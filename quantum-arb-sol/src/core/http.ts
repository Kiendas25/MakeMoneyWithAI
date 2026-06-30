// Shared HTTP layer. One keep-alive undici Pool per host so fan-out fetches
// reuse connections instead of paying TLS setup every tick.

import { Pool } from 'undici';

const pools = new Map<string, Pool>();

function poolFor(origin: string): Pool {
  let p = pools.get(origin);
  if (!p) {
    p = new Pool(origin, {
      connections: 16,
      pipelining: 1,
      keepAliveTimeout: 30_000,
      keepAliveMaxTimeout: 60_000,
    });
    pools.set(origin, p);
  }
  return p;
}

export interface GetJsonOpts {
  timeoutMs?: number;
  headers?: Record<string, string>;
}

/** GET a URL and parse JSON, routed through the per-host keep-alive pool. */
export async function getJson<T>(url: string, opts: GetJsonOpts = {}): Promise<T> {
  const u = new URL(url);
  const pool = poolFor(u.origin);
  const res = await pool.request({
    path: u.pathname + u.search,
    method: 'GET',
    headers: { accept: 'application/json', ...opts.headers },
    headersTimeout: opts.timeoutMs ?? 1500,
    bodyTimeout: opts.timeoutMs ?? 1500,
  });
  if (res.statusCode >= 400) {
    await res.body.dump();
    throw new Error(`GET ${url} -> ${res.statusCode}`);
  }
  return (await res.body.json()) as T;
}

/** Close all pools — call on engine shutdown so the process can exit cleanly. */
export async function closeHttp(): Promise<void> {
  await Promise.all([...pools.values()].map((p) => p.close()));
  pools.clear();
}
