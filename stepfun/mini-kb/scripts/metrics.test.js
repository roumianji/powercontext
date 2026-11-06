import test from 'node:test';
import assert from 'node:assert/strict';
import { percentile, qualityAtK, summarize } from '../src/metrics.js';

test('ranking misses lower quality and duplicate chunks earn no extra relevance', () => {
  const results = ['wrong', 'a', 'a', 'b', 'wrong'].map(source => ({ metadata: { source } }));
  const score = qualityAtK(results, ['a', 'b', 'c']);
  assert.equal(score.recallAt5, 2 / 3);
  assert.equal(score.firstRelevantRank, 2);
  assert.equal(score.reciprocalRank, 0.5);
  assert.ok(score.nDCGAt5 < 0.6);
  assert.equal(qualityAtK([], ['a']).nDCGAt5, 0);
});
test('percentiles interpolate correctly and input is preserved', () => {
  const values = [4, 1, 3, 2];
  assert.equal(percentile(values, 0.5), 2.5);
  assert.ok(Math.abs(percentile(values, 0.95) - 3.85) < 1e-10);
  assert.deepEqual(values, [4, 1, 3, 2]);
  assert.throws(() => percentile([], 0.5));
});
test('only measured trials contribute to aggregate', () => {
  const trials = [1, 3].map(n => ({ embeddingMs: n, searchMs: n * 2, endToEndMs: n * 3, quality: { recallAt5: 1, nDCGAt5: 0.5, reciprocalRank: 0.5 } }));
  const summary = summarize(trials);
  assert.equal(summary.samples, 2);
  assert.equal(summary.embeddingMs.p50, 2);
  assert.equal(summary.quality.nDCGAt5, 0.5);
});
