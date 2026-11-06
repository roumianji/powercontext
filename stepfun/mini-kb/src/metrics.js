export function percentile(values, fraction) {
  if (!values.length || values.some(x => !Number.isFinite(x))) throw new Error('耗时样本必须是非空有限数值');
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * fraction;
  const lower = Math.floor(position);
  return sorted[lower] + (sorted[Math.ceil(position)] - sorted[lower]) * (position - lower);
}

export function qualityAtK(results, relevantSources, k = 5) {
  const relevant = new Set(relevantSources);
  if (!relevant.size) throw new Error('查询必须包含相关文档标注');
  const seen = new Set();
  let hits = 0, dcg = 0, firstRank = null;
  for (const [index, result] of results.slice(0, k).entries()) {
    const source = result.metadata?.source;
    if (relevant.has(source) && !seen.has(source)) {
      hits += 1;
      dcg += 1 / Math.log2(index + 2);
      firstRank ??= index + 1;
      seen.add(source);
    }
  }
  const ideal = Array.from({ length: Math.min(k, relevant.size) }, (_, i) => 1 / Math.log2(i + 2)).reduce((a, b) => a + b, 0);
  return { recallAt5: hits / relevant.size, nDCGAt5: dcg / ideal, reciprocalRank: firstRank ? 1 / firstRank : 0, firstRelevantRank: firstRank };
}

export function summarize(trials) {
  if (!trials.length) throw new Error('没有完成的测评样本');
  const mean = key => trials.reduce((sum, trial) => sum + trial.quality[key], 0) / trials.length;
  const latency = key => ({ p50: percentile(trials.map(t => t[key]), 0.5), p95: percentile(trials.map(t => t[key]), 0.95) });
  return {
    samples: trials.length,
    quality: { recallAt5: mean('recallAt5'), nDCGAt5: mean('nDCGAt5'), mrrAt5: mean('reciprocalRank') },
    embeddingMs: latency('embeddingMs'), seekdbMs: latency('searchMs'), endToEndMs: latency('endToEndMs'),
  };
}
