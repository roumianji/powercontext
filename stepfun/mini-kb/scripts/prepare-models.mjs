import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream } from 'node:fs';
import { mkdir, readFile, rename, rm, stat } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const root = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2);
const option = key => { const index = args.indexOf(key); if (index < 0) return null; if (!args[index+1] || args[index+1].startsWith('--')) throw new Error(`${key} 需要参数`); return args[index+1]; };
const manifest = JSON.parse(await readFile(resolve(root, 'public/model-manifest.json'), 'utf8'));
const directory = resolve(option('--directory') || resolve(root, 'public/models', manifest.model));
const selected = option('--file');
const verifyOnly = args.includes('--verify-only');
const files = Object.entries(manifest.files).filter(([name]) => !selected || name === selected);
if (!files.length) throw new Error('指定文件不在固定模型清单中');
async function verify(path, expected) {
  try {
    if ((await stat(path)).size !== expected.bytes) return false;
    const hash = createHash('sha256');
    for await (const chunk of createReadStream(path)) hash.update(chunk);
    return hash.digest('hex') === expected.sha256;
  } catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}
const endpoints = [...new Set([process.env.HF_ENDPOINT || 'https://huggingface.co', 'https://hf-mirror.com'])];
for (const [name, expected] of files) {
  const target = resolve(directory, name);
  if (await verify(target, expected)) { console.log(`已校验 ${name}`); continue; }
  if (verifyOnly) throw new Error(`${name} 缺失或 SHA256 不一致，请运行 npm run models`);
  await mkdir(dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.part`;
  let lastError, saved = false;
  for (const endpoint of endpoints) {
    for (let attempt = 1; attempt <= 2 && !saved; attempt++) {
      try {
        const base = new URL(endpoint);
        if (base.protocol !== 'https:') throw new Error('HF_ENDPOINT 必须使用 HTTPS');
        const url = `${base.href.replace(/\/$/, '')}/${manifest.model}/resolve/${manifest.revision}/${name}`;
        console.log(`下载 ${name}（${base.hostname}，第 ${attempt} 次）`);
        const response = await fetch(url, { signal: AbortSignal.timeout(300000), redirect: 'follow' });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        await pipeline(Readable.fromWeb(response.body), createWriteStream(temporary));
        if (!await verify(temporary, expected)) throw new Error('下载文件大小或 SHA256 不匹配');
        await rename(temporary, target);
        saved = true;
      } catch (error) { lastError = error; await rm(temporary, { force: true }); }
    }
    if (saved) break;
  }
  if (!saved) throw new Error(`${name} 下载失败：${lastError?.message}`);
}
console.log(`完成：${files.length} 个固定版本文件全部通过 SHA256 校验`);
