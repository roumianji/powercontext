import express from 'express';
import { resolve } from 'node:path';
import { existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SeekdbClient, Schema, FulltextIndexConfig, VectorIndexConfig } from 'seekdb';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const dataPath = resolve(root, 'data', 'seekdb');
mkdirSync(resolve(root, 'data'), { recursive: true });
const client = new SeekdbClient({ path: dataPath, database: 'test' });
const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '12mb' }));
const port = Number(process.env.PORT || 8787);

const profiles = new Set(['fp32', 'fp16', 'q8']);
const validKB = s => typeof s === 'string' && /^[a-z][a-z0-9_]{0,29}$/.test(s);
const collectionName = (kb, profile) => {
  if (!validKB(kb) || !profiles.has(profile)) throw Object.assign(new Error('知识库名称只能使用小写字母、数字、下划线，以字母开头，最多30字符；精度须为 fp32/fp16/q8'), { status: 400 });
  return `stepfun_${kb}_${profile}`;
};
const goodVector = v => Array.isArray(v) && v.length === 384 && v.every(x => typeof x === 'number' && Number.isFinite(x));
const err = (status, msg) => Object.assign(new Error(msg), { status });
const wrap = handler => (req, res, next) => Promise.resolve(handler(req, res)).catch(next);
const schema = () => new Schema()
  .createIndex(new FulltextIndexConfig())
  .createIndex(new VectorIndexConfig({ hnsw: { dimension: 384, distance: 'cosine' }, embeddingFunction: null }));

async function getCollection(kb, profile, create = false) {
  const name = collectionName(kb, profile);
  if (!await client.hasCollection(name)) {
    if (!create) throw err(404, '当前知识库和模型精度尚未导入文档，请先导入');
    return client.createCollection({ name, schema: schema() });
  }
  // Reopen explicitly without the SDK default embedder; vectors come from the browser.
  return client.getCollection({ name, embeddingFunction: null });
}

async function refreshAndVerify(collection, latest) {
  // The database itself flushes asynchronous vector-index work. Never report
  // 'ready' just because an INSERT returned successfully.
  if (typeof collection.refreshIndex === 'function') {
    await collection.refreshIndex();
  } else {
    await client.execute('CALL dbms_index_manager.refresh()');
  }
  const got = await collection.get({ ids: [latest.id], include: ['documents'] });
  if (!got.ids?.includes(latest.id)) throw err(503, '写入未在 seekdb 中确认，请重新尝试');
  const probe = await collection.query({ queryEmbeddings: [latest.embedding], nResults: 20 });
  if (!probe.ids?.[0]?.includes(latest.id)) {
    throw err(503, '向量索引尚未显示新记录，请检查 seekdb 刷新状态后重试');
  }
}

app.get('/api/health', wrap(async (_req, res) => {
  const collections = await client.listCollections({ withEmbeddingFunction: false });
  res.json({ ok: true, engine: 'seekdb-js embedded', collections: collections.length });
}));

app.get('/api/collections', wrap(async (_req, res) => {
  const all = await client.listCollections({ withEmbeddingFunction: false });
  const collections = all.map(x => x.name).filter(x => /^stepfun_[a-z][a-z0-9_]{0,29}_(fp32|fp16|q8)$/.test(x));
  res.json({ collections });
}));

app.post('/api/verify', wrap(async (req, res) => {
  const { kb, profile, ids } = req.body ?? {};
  if (!Array.isArray(ids) || !ids.length || ids.length > 5000 || new Set(ids).size !== ids.length ||
      !ids.every(id => typeof id === 'string' && /^[a-f0-9]{64}$/.test(id))) throw err(400, '待验证的文本块 ID 不合法');
  const collection = await getCollection(kb, profile);
  const found = await collection.get({ ids, include: ['metadatas'] });
  const present = new Set(found.ids || []);
  const missing = ids.filter(id => !present.has(id)).length;
  const count = await collection.count();
  res.json({ count, expected: ids.length, missing, exact: missing === 0 && count === ids.length });
}));

app.post('/api/import', wrap(async (req, res) => {
  const { kb, profile, items } = req.body ?? {};
  collectionName(kb, profile);
  if (!Array.isArray(items) || !items.length || items.length > 32) throw err(400, '每批必须为 1~32 个文本块');
  if (!items.every(x => x && typeof x.id === 'string' && /^[a-f0-9]{64}$/.test(x.id) &&
    typeof x.document === 'string' && x.document.length > 0 && x.document.length <= 3000 &&
    typeof x.source === 'string' && x.source.length <= 255 &&
    Number.isInteger(x.chunk) && x.chunk >= 0 && goodVector(x.embedding))) throw err(400, '文档格式或384维向量校验失败');
  const collection = await getCollection(kb, profile, true);
  const t0 = performance.now();
  await collection.upsert({
    ids: items.map(x => x.id),
    documents: items.map(x => x.document),
    embeddings: items.map(x => x.embedding),
    metadatas: items.map(x => ({ source: x.source, chunk: x.chunk, profile, importedAt: new Date().toISOString() })),
  });
  const writeMs = performance.now() - t0;
  const t1 = performance.now();
  await refreshAndVerify(collection, items[items.length - 1]);
  res.json({ ok: true, written: items.length, writeMs: +writeMs.toFixed(2), refreshAndVerifyMs: +(performance.now() - t1).toFixed(2) });
}));

app.post('/api/search', wrap(async (req, res) => {
  const { kb, profile, query, vector, k = 5 } = req.body ?? {};
  const nResults = Math.min(20, Math.max(1, Number(k) || 5));
  if (typeof query !== 'string' || !query.trim() || query.length > 1000 || !goodVector(vector)) throw err(400, '查询文本或384维向量不合法');
  const collection = await getCollection(kb, profile);
  const t0 = performance.now();
  // Both branches and RRF ranking execute INSIDE seekdb, not in JS.
  const result = await collection.hybridSearch({
    query: { whereDocument: { $contains: query.trim() }, nResults: Math.max(20, nResults) },
    knn: { queryEmbeddings: [vector], nResults: Math.max(20, nResults) },
    rank: { rrf: {} }, nResults,
    include: ['documents', 'metadatas'],
  });
  const searchMs = performance.now() - t0;
  const ids = result.ids?.[0] ?? [];
  const docs = result.documents?.[0] ?? [];
  const metadata = result.metadatas?.[0] ?? [];
  res.json({
    results: ids.map((id, i) => ({ id, document: docs[i] || '', metadata: metadata[i] || {} })),
    searchMs: +searchMs.toFixed(2), mode: 'seekdb.hybridSearch + RRF',
  });
}));

app.use((error, _req, res, _next) => {
  console.error('API error:', error);
  res.status(error.status || 500).json({ error: error.message || '数据库错误' });
});

const dist = resolve(root, 'dist');
if (existsSync(dist)) {
  app.use(express.static(dist));
  app.get('*', (_req, res) => res.sendFile(resolve(dist, 'index.html')));
}
const server = app.listen(port, '127.0.0.1', () => console.log(`Stepfun API: http://127.0.0.1:${port}`));
let closing = false;
const cleanup = async () => {
  if (closing) return;
  closing = true;
  await new Promise(resolve => server.close(resolve));
  await client.close();
  process.exit(0);
};
process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);
