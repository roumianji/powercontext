import { readFileSync, writeFileSync } from 'node:fs';
import { summarize, qualityAtK } from '../src/metrics.js';
const args = process.argv.slice(2), outIndex = args.indexOf('--out');
const output = outIndex < 0 ? null : args.splice(outIndex, 2)[1];
if (!args.length) throw new Error('用法：npm run report -- 日志.json [更多日志.json] [--out 报告.md]');
const runs = args.flatMap(file => {
  const data = JSON.parse(readFileSync(file, 'utf8'));
  if (data.schemaVersion !== 2 || !Array.isArray(data.logs)) throw new Error(`${file}: 需要 v2 原始测评日志`);
  return data.logs.filter(x => x.event === 'benchmark').map(run => ({ ...run, inputFile: file }));
});
if (!runs.length) throw new Error('日志中没有已完成的 benchmark，不生成成绩表');
const groups = new Map();
for (const run of runs) {
  if (!run.corpusHash || !run.queryHash || !run.sessionId || !run.trials?.length || run.trials.length !== run.rounds * new Set(run.trials.map(t => t.queryId)).size) throw new Error('测评身份或逐次记录不完整');
  for (let round = 1; round <= run.rounds; round++) {
    const row = run.trials.filter(t => t.round === round);
    if (row.length !== run.trials.length / run.rounds || new Set(row.map(t => t.queryId)).size !== row.length) throw new Error('正式测量存在缺失或重复查询');
  }
  const stats = summarize(run.trials.map(t => ({ ...t, quality: qualityAtK(t.results, t.relevant) })));
  const signature = JSON.stringify([run.sessionId, run.corpusHash, run.queryHash, run.model, run.revision,
    run.batch, run.topK, run.rounds, run.userAgent, run.hardwareConcurrency]);
  if (!groups.has(signature)) groups.set(signature, new Map());
  groups.get(signature).set(`${run.backend}/${run.profile}/${run.current.backendPolicy}`, { ...run, stats });
}
const lines = ['# 阶跃星辰端侧检索实测报告', '', '以下数值仅从导出的正式查询逐次记录计算；预热和模型加载不计入热态延迟。', '',
  '扩展集是项目自建英文合成回归集，标注未经独立人工复核，不属于公开标准基准。仅 WASM 配置验证禁用 GPU 路径，不能替代对 GPU 失败时自动降级的故障注入测试。', ''];
let groupNumber = 0;
for (const group of groups.values()) {
  const values = [...group.values()], first = values[0];
  lines.push(`## 对照组 ${++groupNumber}`, '', `测评集：${first.suiteId}；${first.corpusChunks} 块；batch=${first.batch}；每组 ${first.stats.samples} 次正式查询。`, '',
    `语料 SHA256：\`${first.corpusHash}\`；查询与标注 SHA256：\`${first.queryHash}\`。`, '',
    `浏览器：${first.userAgent}；逻辑线程：${first.hardwareConcurrency}。`, '',
    '| 实际后端 / 精度 | 权重 MiB | 向量化 P50 / P95 ms | seekdb P50 / P95 ms | 端到端 P50 / P95 ms | Recall@5 | nDCG@5 | MRR@5 |',
    '|---|---:|---:|---:|---:|---:|---:|---:|');
  const fixed = value => Number(value).toFixed(3), pair = value => `${fixed(value.p50)} / ${fixed(value.p95)}`;
  for (const run of values) {
    const s = run.stats, bytes = run.current.weights?.bytes;
    lines.push(`| ${run.backend} / ${run.profile} (${run.current.backendPolicy}) | ${bytes ? fixed(bytes/1048576) : '未记录'} | ${pair(s.embeddingMs)} | ${pair(s.seekdbMs)} | ${pair(s.endToEndMs)} | ${fixed(s.quality.recallAt5)} | ${fixed(s.quality.nDCGAt5)} | ${fixed(s.quality.mrrAt5)} |`);
  }
  const baseline = values.find(x => x.profile === 'fp32' && x.backend === 'webgpu');
  const optimized = values.find(x => x.profile === 'fp16' && x.backend === 'webgpu');
  if (baseline && optimized) lines.push('', `同后端 FP32 / FP16 查询向量化 P50 比值：${fixed(baseline.stats.embeddingMs.p50 / optimized.stats.embeddingMs.p50)}；小于 1 表示本轮 FP16 更慢。`,
    `Recall@5 变化：${fixed(optimized.stats.quality.recallAt5 - baseline.stats.quality.recallAt5)}；nDCG@5 变化：${fixed(optimized.stats.quality.nDCGAt5 - baseline.stats.quality.nDCGAt5)}。`);
  if (baseline && optimized) lines.push('', `FP16 的查询向量化 P95 为 ${fixed(optimized.stats.embeddingMs.p95)} ms，${optimized.stats.embeddingMs.p95 > baseline.stats.embeddingMs.p95 ? '高于' : optimized.stats.embeddingMs.p95 < baseline.stats.embeddingMs.p95 ? '低于' : '等于'} FP32 的 ${fixed(baseline.stats.embeddingMs.p95)} ms。单项指标变化不能替代重复实验和稳定性验证。`);
  const misses = new Map();
  for (const run of values) for (const trial of run.trials) if (qualityAtK(trial.results, trial.relevant).recallAt5 < 1) misses.set(trial.queryId, trial.query);
  if (misses.size) lines.push('', '未完全召回的查询：', ...[...misses].map(([id, query]) => `- ${id}: ${query}`), '');
  lines.push('', '同一对照组固定了会话、语料、查询、模型、batch、轮数、浏览器及线程数。WASM 与 WebGPU 后端不同，不能把其差异仅归因于数值精度。', '');
}
const markdown = lines.join('\n')+'\n';
if (output) { writeFileSync(output, markdown); console.log(`已保存 ${output}`); } else console.log(markdown);
