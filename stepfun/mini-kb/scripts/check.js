import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
const root = fileURLToPath(new URL('..', import.meta.url));
const files = ['vite.config.js'];
for (const dir of ['src', 'server', 'scripts']) for (const name of readdirSync(join(root, dir))) if (/\.m?js$/.test(name)) files.push(`${dir}/${name}`);
for (const file of files) {
  const result = spawnSync(process.execPath, ['--check', join(root, file)], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`Syntax checked ${files.length} JavaScript files`);
