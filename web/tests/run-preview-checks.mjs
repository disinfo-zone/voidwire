import { spawn } from 'node:child_process';
import process from 'node:process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = process.env.SMOKE_PORT || '4510';
const BASE_URL = `http://127.0.0.1:${PORT}`;
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ASTRO_BIN = process.platform === 'win32'
  ? path.join(ROOT, 'node_modules', '.bin', 'astro.cmd')
  : path.join(ROOT, 'node_modules', '.bin', 'astro');

function runCommand(command, args, env = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: ROOT,
      env: { ...process.env, ...env },
      stdio: 'inherit',
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(' ')} exited with code ${code}`));
    });
  });
}

async function waitForPreview(preview) {
  const timeoutAt = Date.now() + 25000;
  let buffered = '';
  return await new Promise((resolve, reject) => {
    const onData = (chunk) => {
      buffered += chunk.toString();
      if (buffered.includes('Server listening')) {
        cleanup();
        resolve();
      }
      if (Date.now() > timeoutAt) {
        cleanup();
        reject(new Error(`Timed out waiting for preview server. Output:\n${buffered}`));
      }
    };
    const onExit = (code) => {
      cleanup();
      reject(new Error(`Preview exited early with code ${code}. Output:\n${buffered}`));
    };
    const cleanup = () => {
      preview.stdout?.off('data', onData);
      preview.stderr?.off('data', onData);
      preview.off('exit', onExit);
    };
    preview.stdout?.on('data', onData);
    preview.stderr?.on('data', onData);
    preview.on('exit', onExit);
  });
}

async function stopPreview(preview) {
  if (!preview || preview.pid == null || preview.exitCode !== null) return;
  if (process.platform === 'win32') {
    try {
      await runCommand('taskkill', ['/pid', String(preview.pid), '/t', '/f']);
    } catch {
      // Ignore cleanup failures.
    }
    return;
  }
  preview.kill('SIGINT');
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (preview.exitCode === null) {
    preview.kill('SIGKILL');
  }
}

async function run() {
  const previewCommand = process.platform === 'win32'
    ? `"${ASTRO_BIN}" preview --host 127.0.0.1 --port ${PORT}`
    : ASTRO_BIN;
  const previewArgs = process.platform === 'win32'
    ? []
    : ['preview', '--host', '127.0.0.1', '--port', PORT];
  const preview = spawn(previewCommand, previewArgs, {
    cwd: ROOT,
    env: { ...process.env },
    shell: process.platform === 'win32',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  preview.stdout?.pipe(process.stdout);
  preview.stderr?.pipe(process.stderr);

  try {
    await waitForPreview(preview);
    await runCommand(process.execPath, ['tests/smoke-routes.mjs'], { SMOKE_BASE_URL: BASE_URL });
    await runCommand(process.execPath, ['tests/visual/snapshots.mjs'], { SMOKE_BASE_URL: BASE_URL });
  } finally {
    await stopPreview(preview);
  }
}

run().catch((err) => {
  console.error('Preview checks failed:', err);
  process.exit(1);
});
