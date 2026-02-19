import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const BASE_URL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:4510';
const UPDATE = process.argv.includes('--update');
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const BASELINE_DIR = path.join(ROOT, 'baselines');

const SNAPSHOTS = [
  { name: 'chart-orientation.png', route: '/og/2026-02-19.png' },
  { name: 'moon-card-mobile-360.png', route: '/qa/moon-card/0.25.png?width=360' },
  { name: 'moon-card-mobile-390.png', route: '/qa/moon-card/0.75.png?width=390' },
];

function sha256(data) {
  return createHash('sha256').update(data).digest('hex');
}

async function fetchBuffer(route) {
  const res = await fetch(`${BASE_URL}${route}`);
  if (!res.ok) {
    throw new Error(`${route} returned HTTP ${res.status}`);
  }
  const data = new Uint8Array(await res.arrayBuffer());
  return Buffer.from(data);
}

async function run() {
  await mkdir(BASELINE_DIR, { recursive: true });
  const failures = [];

  for (const snapshot of SNAPSHOTS) {
    const actual = await fetchBuffer(snapshot.route);
    const baselinePath = path.join(BASELINE_DIR, snapshot.name);

    if (UPDATE) {
      await writeFile(baselinePath, actual);
      console.log(`updated ${snapshot.name}`);
      continue;
    }

    let expected;
    try {
      expected = await readFile(baselinePath);
    } catch {
      failures.push(`${snapshot.name} baseline is missing (run: node tests/visual/snapshots.mjs --update)`);
      continue;
    }

    const actualHash = sha256(actual);
    const expectedHash = sha256(expected);
    if (actualHash !== expectedHash) {
      failures.push(`${snapshot.name} changed (expected ${expectedHash}, got ${actualHash})`);
    }
  }

  if (failures.length > 0) {
    console.error('Visual snapshots failed:');
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
  }

  if (!UPDATE) {
    console.log(`Visual snapshots passed (${BASE_URL})`);
  }
}

run().catch((err) => {
  console.error('Visual snapshot test crashed:', err);
  process.exit(1);
});
