import { pipeline, env } from '@huggingface/transformers';

// Browser worker exclusively: the backend never imports or executes any model.
env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = '/models/';
const MODEL = 'Xenova/all-MiniLM-L6-v2';
const REVISION = '751bff3';
let embedder = null;
let active = null;

function notify(id, type, payload) { self.postMessage({ id, type, ...payload }); }
async function load(id, mode, backendPolicy = 'auto') {
  if (!['baseline', 'optimized'].includes(mode) || !['auto', 'wasm'].includes(backendPolicy)) throw new Error('未知模型配置');
  if (active?.mode === mode && active?.backendPolicy === backendPolicy && embedder) return { ...active, model: MODEL, revision: REVISION, reused: true };
  if (embedder?.dispose) await embedder.dispose();
  embedder = null;
  active = null;
  const failures = [];
  let adapterInfo = null;
  const candidates = [];
  if (backendPolicy !== 'wasm' && typeof navigator !== 'undefined' && navigator.gpu) {
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (adapter?.info) adapterInfo = { vendor: adapter.info.vendor, architecture: adapter.info.architecture, device: adapter.info.device, description: adapter.info.description };
      if (adapter) candidates.push({ backend: 'webgpu', profile: mode === 'baseline' ? 'fp32' : 'fp16' });
    } catch { /* WASM fallback */ }
  }
  candidates.push({ backend: 'wasm', profile: mode === 'baseline' ? 'fp32' : 'q8' });
  let lastError;
  for (const candidate of candidates) {
    try {
      notify(id, 'status', { message: `加载 ${MODEL} ${candidate.profile} / ${candidate.backend}（从本机静态目录加载）` });
      embedder = await pipeline('feature-extraction', MODEL, {
        revision: REVISION,
        device: candidate.backend,
        dtype: candidate.profile,
        progress_callback: (event) => {
          if (event.status === 'progress') notify(id, 'progress', { loaded: event.loaded, total: event.total, file: event.file });
        },
      });
      active = { ...candidate, mode, backendPolicy, adapterInfo, failures };
      return { ...active, model: MODEL, revision: REVISION, reused: false };
    } catch (e) {
      lastError = e;
      failures.push({ ...candidate, error: String(e.message || e) });
      notify(id, 'status', { message: `${candidate.backend}/${candidate.profile} 不可用：${String(e.message || e)}；尝试备用后端` });
      if (embedder?.dispose) await embedder.dispose().catch(() => {});
      embedder = null;
    }
  }
  active = null;
  throw new Error('WebGPU / WASM 均无法加载模型：' + (lastError?.message || lastError));
}
self.onmessage = async event => {
  const { id, task, mode, backendPolicy, texts } = event.data;
  try {
    if (task === 'load') {
      const start = performance.now();
      const info = await load(id, mode, backendPolicy);
      notify(id, 'result', { result: { ...info, modelLoadMs: +(performance.now() - start).toFixed(2) } });
      return;
    }
    if (task === 'embed') {
      if (!embedder) throw new Error('请先加载模型');
      if (!Array.isArray(texts) || !texts.length || texts.length > 32) throw new Error('每次最多32条');
      const start = performance.now();
      const tensor = await embedder(texts, { pooling: 'mean', normalize: true });
      const vectors = tensor.tolist();
      tensor.dispose?.();
      if (vectors.length !== texts.length || vectors.some(v => v.length !== 384)) throw new Error('embedding 维度与输入不匹配');
      notify(id, 'result', { result: { vectors, embeddingMs: +(performance.now() - start).toFixed(2) } });
      return;
    }
    throw new Error('未知任务');
  } catch (e) { notify(id, 'error', { error: String(e?.message || e) }); }
};
