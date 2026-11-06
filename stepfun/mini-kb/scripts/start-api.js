import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { diagnostic } from '../server/diagnostics.js';

// Reserve static TLS before the API process starts. Keep native loading with the SDK.
const childEnv = { ...process.env };
if (process.platform === 'linux') {
  childEnv.GLIBC_TUNABLES = (childEnv.GLIBC_TUNABLES || '').split(':')
    .filter(value => value && !value.startsWith('glibc.rtld.optional_static_tls='))
    .concat('glibc.rtld.optional_static_tls=65536').join(':');
}
const watch = process.argv.includes('--watch') || process.env.NODE_ENV !== 'production';
const entry = fileURLToPath(new URL('../server/app.js', import.meta.url));
const log = createWriteStream(fileURLToPath(new URL('../data/api-process.log', import.meta.url)), { flags: 'a' });
diagnostic('launching_api', { childGlibcTunables: childEnv.GLIBC_TUNABLES, nativePreloaded: false, watch });
const child = spawn(process.execPath, [...(watch ? ['--watch'] : []), entry], { env: childEnv, stdio: ['inherit', 'pipe', 'pipe'] });
child.stdout.on('data', value => { process.stdout.write(value); log.write(value); });
child.stderr.on('data', value => { process.stderr.write(value); log.write(value); });
let stopping = false;
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { stopping = true; child.kill(signal); });
child.on('error', error => { diagnostic('launch_error', { error: error.stack }); console.error(error); log.end(); process.exitCode = 1; });
child.on('exit', (code, signal) => { diagnostic('api_exit', { code, signal }); log.end(); process.exitCode = code ?? (stopping ? 0 : 1); });
