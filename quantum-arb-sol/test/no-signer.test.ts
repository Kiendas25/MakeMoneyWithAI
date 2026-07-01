// Guard rail enforced as a test: the codebase must contain NO transaction
// signing / sending surface. If anyone wires a signer, keypair, or sendTransaction
// into src/, this fails and blocks the build.

import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../src', import.meta.url));

const FORBIDDEN = [
  /sendTransaction/,
  /sendRawTransaction/,
  /signTransaction/,
  /Keypair\s*\.\s*fromSecretKey/,
  /Keypair\s*\.\s*generate/,
  /from\s+['"]@solana\/web3\.js['"]/, // no signing SDK imports at all
  /PRIVATE_KEY/,
  /SECRET_KEY/,
  /MNEMONIC/,
];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(ts|tsx)$/.test(p)) out.push(p);
  }
  return out;
}

describe('no signer / sender in the codebase', () => {
  it('contains no transaction signing or sending symbols', () => {
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      if (file.endsWith('no-signer.test.ts')) continue;
      const text = readFileSync(file, 'utf8');
      for (const rx of FORBIDDEN) {
        if (rx.test(text)) offenders.push(`${file} :: ${rx}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
