import './style.css';
import { summarize, qualityAtK } from './metrics.js';
const $ = id => document.getElementById(id);
const worker = new Worker(new URL('./embedding.worker.js', import.meta.url), { type: 'module' });
const requests = new Map(), sessionId = crypto.randomUUID(), STORAGE_KEY = 'stepfun-evidence-v2';
let requestId = 0, current = null, busy = false, logs = [];
try { logs = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); if (!Array.isArray(logs)) logs = []; } catch { logs = []; }
const fmt = value => `${Number(value).toFixed(2)} ms`;
const setStatus = (id, text, error = false) => { $(id).textContent = text; $(id).classList.toggle('error', error); };
function record(entry) {
  logs.push({ ...entry, timestamp: new Date().toISOString(), sessionId });
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(logs)); $('log-status').textContent = `本浏览器已保存 ${logs.length} 条记录，刷新后仍可导出。`; }
  catch { $('log-status').textContent = '浏览器存储不可用或已满，请立即导出 JSON。'; }
}
function setBusy(value) {
  busy = value;
  for (const element of document.querySelectorAll('button, input, select, textarea')) if (element.id !== 'export') element.disabled = value;
}
async function action(statusId, task) {
  if (busy) return;
  setBusy(true);
  try { await task(); } catch (error) { setStatus(statusId, error.message, true); }
  finally { setBusy(false); }
}
worker.onmessage = ({ data }) => {
  const request = requests.get(data.id);
  if (!request) return;
  if (data.type === 'status') setStatus('model-status', data.message);
  else if (data.type === 'progress') setStatus('model-status', `加载本地模型 ${data.file || ''}${data.total ? ` (${Math.round(data.loaded / data.total * 100)}%)` : ''}`);
  else if (data.type === 'result' || data.type === 'error') {
    clearTimeout(request.timer); requests.delete(data.id);
    if (data.type === 'result') request.resolve(data.result); else request.reject(new Error(data.error));
  }
};
function failWorker(error) {
  for (const request of requests.values()) { clearTimeout(request.timer); request.reject(new Error(error.message || 'Worker 已停止，请刷新页面')); }
  requests.clear(); current = null;
}
worker.onerror = failWorker;
worker.onmessageerror = () => failWorker(new Error('Worker 消息解析失败，请刷新页面'));
function work(task, args = {}) {
  return new Promise((resolve, reject) => {
    const id = ++requestId;
    const timer = setTimeout(() => { requests.delete(id); current = null; reject(new Error('模型操作超时，请刷新页面后重试')); }, 180000);
    requests.set(id, { resolve, reject, timer }); worker.postMessage({ id, task, ...args });
  });
}
async function api(path, body) {
  const response = await fetch(`/api/${path}`, { ...(body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }), signal: AbortSignal.timeout(120000) });
  const payload = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}
function kb() {
  const value = $('kb').value.trim();
  if (!/^[a-z][a-z0-9_]{0,29}$/.test(value)) throw new Error('知识库 ID 必须以小写字母开头，只能包含 a-z / 0-9 / _，不超过30字符');
  return value;
}
function requireModel() {
  if (!current || $('mode').value !== current.mode || $('backend-policy').value !== current.backendPolicy) throw new Error('请先加载当前配置的模型');
}
function chunkText(text, maxChars = 380, overlap = 55) {
  const normalized = text.replace(/\r\n?/g, '\n').trim(), chunks = [];
  for (let start = 0; start < normalized.length;) {
    const end = Math.min(normalized.length, start + maxChars), part = normalized.slice(start, end).trim();
    if (part) chunks.push(part);
    if (end >= normalized.length) break;
    start = end - overlap;
  }
  return chunks;
}
async function sha256(value) {
  const buffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return [...new Uint8Array(buffer)].map(b => b.toString(16).padStart(2, '0')).join('');
}
async function prepareDocuments(documents, knowledgeBase) {
  const chunks = [];
  for (const document of documents) for (const [index, text] of chunkText(document.text).entries()) chunks.push({
    id: await sha256(`${knowledgeBase}\u0000${document.source}\u0000${index}\u0000${text}`),
    document: text, source: document.source, chunk: index,
  });
  if (!chunks.length) throw new Error('文档内容为空');
  return chunks;
}
async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`无法读取测评资源：${url}`);
  return response.json();
}
async function suite() {
  let data;
  if ($('suite').value === 'extended') data = await readJson('/evaluation-suite.json');
  else {
    const tests = [
      ['How does seekdb refresh vector indexes?', 'index_refresh.txt'],
      ['What is the use of GPU in machine learning?', 'gpu_inference.txt'],
      ['Why should documents be split into chunks?', 'document_chunking.txt'],
      ['What is reciprocal rank fusion used for?', 'hybrid_search.txt'],
      ['How do you keep private content on the local device?', 'local_privacy.txt'],
    ];
    const documents = [];
    for (const [, source] of tests) {
      const response = await fetch(`/${source}`);
      if (!response.ok) throw new Error(`找不到样例 ${source}`);
      documents.push({ source, text: await response.text() });
    }
    data = { id: 'smoke-five-v1', label: '冒烟：5 文档 / 5 查询', description: '仅验证流程；五文档时 Recall@5 区分度很低。', documents,
      queries: tests.map(([query, source], i) => ({ id: `smoke-${i+1}`, query, relevant: [source] })) };
  }
  const corpusHash = await sha256(JSON.stringify(data.documents)), queryHash = await sha256(JSON.stringify(data.queries));
  return { ...data, corpusHash, queryHash, kb: `eval_${corpusHash.slice(0, 12)}` };
}
async function listCollections() {
  const { collections } = await api('collections');
  $('collections').replaceChildren(new Option('选择已有集合', ''));
  for (const name of collections.sort()) $('collections').add(new Option(name, name));
}
async function activateModel() {
  current = null;
  const mode = $('mode').value, backendPolicy = $('backend-policy').value;
  try {
    const info = await work('load', { mode, backendPolicy });
    current = { ...info, mode, backendPolicy };
    try { current.weights = (await readJson('/model-manifest.json')).profiles[info.profile]; } catch { current.weights = null; }
    $('backend').textContent = `${info.backend.toUpperCase()} / ${info.profile.toUpperCase()}`;
    $('model-stats').textContent = `模型：${info.model} | revision：${info.revision} | 本次加载：${fmt(info.modelLoadMs)}${current.weights ? ` | 权重：${(current.weights.bytes / 1048576).toFixed(2)} MiB` : ''}`;
    setStatus('model-status', `${info.backend === 'webgpu' ? '使用 WebGPU 加速' : backendPolicy === 'wasm' ? '按所选配置使用 WASM' : 'WebGPU 不可用或初始化失败，已降级为 WASM'}。向量化在浏览器本地执行。`);
    record({ event: 'model_load', current, userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency });
  } catch (error) { $('backend').textContent = '加载失败'; throw error; }
  // A database error must not discard a successfully initialized browser model.
  await renderComparison();
listCollections().catch(error => setStatus('import-status', `模型已加载；seekdb API 尚未就绪：${error.message}`, true));
}
async function importDocuments(documents, knowledgeBase, identity = {}) {
  requireModel();
  const docs = await prepareDocuments(documents, knowledgeBase), batch = Number($('batch').value);
  const summary = { event: 'import', ...identity, model: current.model, revision: current.revision,
    profile: current.profile, backend: current.backend, kb: knowledgeBase, batch, chunks: docs.length,
    embeddingMs: 0, writeMs: 0, refreshAndVerifyMs: 0 };
  const start = performance.now();
  for (let i = 0; i < docs.length; i += batch) {
    const slice = docs.slice(i, i + batch);
    setStatus('import-status', `本地向量化并导入 ${i + 1}–${i + slice.length}/${docs.length} 文本块`);
    const encoded = await work('embed', { texts: slice.map(x => x.document) });
    summary.embeddingMs += encoded.embeddingMs;
    const saved = await api('import', { kb: knowledgeBase, profile: current.profile,
      items: slice.map((item, n) => ({ ...item, embedding: encoded.vectors[n] })) });
    summary.writeMs += saved.writeMs; summary.refreshAndVerifyMs += saved.refreshAndVerifyMs;
  }
  summary.totalMs = performance.now() - start;
  summary.throughput = docs.length / (summary.embeddingMs / 1000); record(summary);
  setStatus('import-status', `导入完成：${docs.length} 块；每批均经过 seekdb 写入、刷新和可检索性验证。`);
  $('import-stats').textContent = `Embedding ${fmt(summary.embeddingMs)} | 写入 ${fmt(summary.writeMs)} | 刷新/验证 ${fmt(summary.refreshAndVerifyMs)} | ${summary.throughput.toFixed(2)} 块/秒`;
  await listCollections();
}
async function importFiles() {
  const files = [...$('files').files], documents = [];
  if (!files.length) throw new Error('请选择至少一个 .txt / .md 文件');
  for (const file of files) {
    if (!/\.(txt|md)$/i.test(file.name) || file.size > 2 * 1024 * 1024) throw new Error(`文件格式或大小不符合要求：${file.name}`);
    documents.push({ source: file.name, text: await file.text() });
  }
  await importDocuments(documents, kb());
}
async function importSuite(data) {
  $('kb').value = data.kb;
  await work('embed', { texts: data.documents.slice(0, Number($('batch').value)).map(x => x.text) });
  await importDocuments(data.documents, data.kb, { suiteId: data.id, corpusHash: data.corpusHash, warmedUp: true });
}
async function searchOne(query, display = false) {
  requireModel();
  const start = performance.now(), encoded = await work('embed', { texts: [query] });
  const response = await api('search', { kb: kb(), profile: current.profile, query, vector: encoded.vectors[0], k: 5 });
  const result = { query, profile: current.profile, backend: current.backend, kb: kb(), embeddingMs: encoded.embeddingMs,
    searchMs: response.searchMs, endToEndMs: performance.now() - start, results: response.results };
  if (display) {
    $('results').replaceChildren();
    for (const [index, item] of result.results.entries()) {
      const container = document.createElement('div'); container.className = 'result';
      const source = document.createElement('div'); source.className = 'source';
      source.textContent = `#${index + 1} · ${item.metadata.source || '未命名'} · chunk ${item.metadata.chunk ?? '-'}`;
      const body = document.createElement('div'); body.className = 'body'; body.textContent = item.document;
      container.append(source, body); $('results').append(container);
    }
    $('search-stats').textContent = `查询向量化 ${fmt(result.embeddingMs)} | seekdb ${fmt(result.searchMs)} | 端到端 ${fmt(result.endToEndMs)}`;
    setStatus('search-status', `${response.mode} · ${result.results.length} 条结果`);
  }
  return result;
}
async function benchmark(data) {
  requireModel();
  if (kb() !== data.kb) throw new Error('请先导入固定测评语料，使用与查询匹配的知识库');
  const docs = await prepareDocuments(data.documents, data.kb);
  const verification = await api('verify', { kb: data.kb, profile: current.profile, ids: docs.map(d => d.id) });
  if (!verification.exact) throw new Error(`集合与固定语料不一致（实际 ${verification.count} 块，预期 ${docs.length} 块，缺失 ${verification.missing} 块），请先导入`);
  const rounds = Number($('rounds').value), warmupTrials = [], trials = [], runId = crypto.randomUUID();
  for (let i = 0; i < 3; ++i) {
    setStatus('benchmark-status', `预热 ${i+1}/3（不计入统计）`);
    warmupTrials.push(await searchOne(data.queries[i % data.queries.length].query));
  }
  record({ event: 'warmup', runId, suiteId: data.id, profile: current.profile, backend: current.backend, trials: warmupTrials });
  for (let round = 0; round < rounds; ++round) for (let offset = 0; offset < data.queries.length; ++offset) {
    const test = data.queries[(offset + round) % data.queries.length];
    setStatus('benchmark-status', `${current.profile.toUpperCase()} · 第 ${round+1}/${rounds} 轮 · ${offset+1}/${data.queries.length} 查询`);
    const result = await searchOne(test.query);
    trials.push({ ...result, round: round+1, queryId: test.id, relevant: test.relevant, quality: qualityAtK(result.results, test.relevant) });
  }
  const summary = { event: 'benchmark', runId, suiteId: data.id, suiteDescription: data.description,
    corpusHash: data.corpusHash, queryHash: data.queryHash, kb: data.kb, corpusChunks: docs.length,
    model: current.model, revision: current.revision, current, profile: current.profile, backend: current.backend,
    batch: Number($('batch').value), rounds, topK: 5, warmupCount: warmupTrials.length,
    userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, ...summarize(trials), trials };
  record(summary); renderComparison();
  setStatus('benchmark-status', `${summary.samples} 次正式测评完成 | Recall@5 ${summary.quality.recallAt5.toFixed(3)} | nDCG@5 ${summary.quality.nDCGAt5.toFixed(3)}\n查询向量化 P50 / P95：${fmt(summary.embeddingMs.p50)} / ${fmt(summary.embeddingMs.p95)}\nseekdb P50 / P95：${fmt(summary.seekdbMs.p50)} / ${fmt(summary.seekdbMs.p95)}\n端到端 P50 / P95：${fmt(summary.endToEndMs.p50)} / ${fmt(summary.endToEndMs.p95)}\n原始逐次记录已保存，请导出 JSON。`);
}
function renderComparison() {
  const body = $('comparison-body'); body.replaceChildren();
  const completed = logs.filter(x => x.event === 'benchmark');
  const latestSession = completed.at(-1)?.sessionId;
  for (const entry of completed.filter(x => x.sessionId === latestSession)) {
    const row = document.createElement('tr');
    for (const value of [`${entry.backend} / ${entry.profile}`, entry.suiteId, entry.samples, entry.embeddingMs.p50.toFixed(2),
      entry.seekdbMs.p50.toFixed(2), entry.endToEndMs.p50.toFixed(2), entry.quality.recallAt5.toFixed(3), entry.quality.nDCGAt5.toFixed(3)]) {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    body.append(row);
  }
  if (!current && completed.length) setStatus('benchmark-status', `已恢复上次完成的 ${completed.filter(x => x.sessionId === latestSession).length} 组实测，详情见下表与原始日志。`);
}
async function matrix() {
  const data = await suite();
  for (const config of [{ mode: 'baseline', policy: 'auto' }, { mode: 'optimized', policy: 'auto' }, { mode: 'optimized', policy: 'wasm' }]) {
    $('mode').value = config.mode; $('backend-policy').value = config.policy;
    setStatus('matrix-status', `正在运行 ${config.mode} / ${config.policy}：加载 → 导入 → 预热 → 正式测评`);
    await activateModel(); await importSuite(data); await benchmark(data);
  }
  setStatus('matrix-status', '三组配置完成。请检查实际后端并导出原始记录；GPU 不可用时自动配置会降级，请以日志为准。');
}
function exportLogs() {
  const value = { schemaVersion: 2, generatedAt: new Date().toISOString(), sessionId,
    userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, current, logs };
  const href = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = href; anchor.download = `stepfun-benchmark-${Date.now()}.json`; anchor.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
$('load').addEventListener('click', () => action('model-status', activateModel));
$('import').addEventListener('click', () => action('import-status', importFiles));
$('import-suite').addEventListener('click', () => action('import-status', async () => { requireModel(); await importSuite(await suite()); }));
$('search').addEventListener('click', () => action('search-status', async () => {
  const query = $('query').value.trim(); if (!query) throw new Error('请输入查询');
  record({ event: 'search', ...await searchOne(query, true) });
}));
$('benchmark').addEventListener('click', () => action('benchmark-status', async () => benchmark(await suite())));
$('matrix').addEventListener('click', () => action('matrix-status', matrix));
$('export').addEventListener('click', exportLogs);
$('refresh-collections').addEventListener('click', () => action('import-status', listCollections));
for (const id of ['mode', 'backend-policy']) $(id).addEventListener('change', () => {
  current = null; $('backend').textContent = '待重新加载'; setStatus('model-status', '配置已更改，请重新加载模型');
});
$('collections').addEventListener('change', () => {
  const match = $('collections').value.match(/^stepfun_([a-z][a-z0-9_]{0,29})_(fp32|fp16|q8)$/);
  if (!match) return;
  $('kb').value = match[1];
  if (current && current.profile !== match[2]) setStatus('model-status', `所选集合是 ${match[2]}，当前模型是 ${current.profile}；请切换相应模型配置`, true);
});
$('log-status').textContent = `本浏览器已有 ${logs.length} 条记录，可导出。`;
renderComparison();
listCollections().catch(error => setStatus('import-status', `seekdb API 尚未就绪：${error.message}`, true));
