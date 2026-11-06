import { writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const data = fileURLToPath(new URL('../data/', import.meta.url));
mkdirSync(data, { recursive: true });
export function diagnostic(phase, details = {}) {
  writeFileSync(`${data}/api-startup.json`, JSON.stringify({ phase, timestamp: new Date().toISOString(),
    node: process.version, platform: process.platform, arch: process.arch, pid: process.pid,
    glibcTunables: process.env.GLIBC_TUNABLES || '', ...details }, null, 2));
}
