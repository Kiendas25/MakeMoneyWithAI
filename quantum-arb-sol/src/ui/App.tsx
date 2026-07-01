// Minimal read-only dashboard. Connects to the engine's local WS server and
// renders live spreads, opportunities, and paper PnL per pair. No controls that
// could trigger execution — the engine exposes no command channel.

import { useEffect, useState } from 'react';
import { useEngineSocket } from './useEngineSocket.js';

const WS_URL = `ws://localhost:${import.meta.env.VITE_ENGINE_WS_PORT ?? 8787}`;

export default function App() {
  const { connected, quotesByPair, opportunities, ledger, lastMetric, notionalUsd, setNotional } =
    useEngineSocket(WS_URL);

  // Local input mirrors the engine's global notional; applying sends it back.
  const [draft, setDraft] = useState('');
  useEffect(() => {
    if (notionalUsd > 0 && draft === '') setDraft(String(notionalUsd));
  }, [notionalUsd, draft]);

  const apply = () => {
    const n = Number(draft);
    if (Number.isFinite(n) && n > 0) setNotional(n);
  };

  return (
    <div style={S.page}>
      <header style={S.header}>
        <h1 style={S.h1}>Quantum-Arb-SOL</h1>
        <span style={S.tag}>simulation · backtest · paper-trade — no real execution</span>
        <span style={{ ...S.dot, background: connected ? '#21c074' : '#c0392b' }} />
      </header>

      <div style={S.controls}>
        <label style={S.label}>Montante por trade (USD)</label>
        <input
          style={S.input}
          type="number"
          min={1}
          step={100}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && apply()}
        />
        <button style={S.btn} onClick={apply} disabled={!connected}>
          Aplicar
        </button>
        <span style={S.current}>atual: ${notionalUsd.toLocaleString()}</span>
      </div>

      {lastMetric && (
        <div style={S.metrics}>
          tick {lastMetric.tick} · quotes {lastMetric.quotes} · opp {lastMetric.opportunities} ·
          fills {lastMetric.fills} · {lastMetric.durationMs.toFixed(1)}ms · dropped{' '}
          {lastMetric.droppedTicks}
        </div>
      )}

      <section style={S.grid}>
        <Panel title="Spreads by pair">
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Pair</th>
                <th style={S.th}>Best bid</th>
                <th style={S.th}>Best ask</th>
                <th style={S.th}>Venues</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(quotesByPair).map(([key, qs]) => {
                const bestBid = Math.max(...qs.map((q) => q.bid));
                const bestAsk = Math.min(...qs.map((q) => q.ask));
                return (
                  <tr key={key}>
                    <td style={S.td}>{key}</td>
                    <td style={S.td}>{bestBid.toFixed(4)}</td>
                    <td style={S.td}>{bestAsk.toFixed(4)}</td>
                    <td style={S.td}>{qs.length}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>

        <Panel title="Live opportunities (net bps)">
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Pair</th>
                <th style={S.th}>Buy</th>
                <th style={S.th}>Sell</th>
                <th style={S.th}>Net bps</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.slice(0, 20).map((o, i) => (
                <tr key={`${o.pair.key}-${i}`}>
                  <td style={S.td}>{o.pair.key}</td>
                  <td style={S.td}>{o.buyVenue}</td>
                  <td style={S.td}>{o.sellVenue}</td>
                  <td style={{ ...S.td, color: o.netBps > 0 ? '#21c074' : '#c0392b' }}>
                    {o.netBps.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Paper PnL">
          <div style={S.pnl}>${ledger?.realizedPnlUsd.toFixed(2) ?? '0.00'}</div>
          <div style={S.sub}>
            {ledger?.fills ?? 0} fills · {ledger?.openPositions ?? 0} open
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={S.panel}>
      <div style={S.panelTitle}>{title}</div>
      {children}
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  page: { fontFamily: 'ui-monospace, monospace', background: '#0d1117', color: '#e6edf3', minHeight: '100vh', padding: 20 },
  header: { display: 'flex', alignItems: 'center', gap: 12 },
  h1: { fontSize: 20, margin: 0 },
  tag: { fontSize: 12, color: '#8b949e' },
  dot: { width: 10, height: 10, borderRadius: '50%', marginLeft: 'auto' },
  metrics: { fontSize: 12, color: '#8b949e', margin: '12px 0' },
  controls: { display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', margin: '14px 0', padding: 12, background: '#161b22', border: '1px solid #30363d', borderRadius: 8 },
  label: { fontSize: 13, color: '#8b949e' },
  input: { background: '#0d1117', color: '#e6edf3', border: '1px solid #30363d', borderRadius: 6, padding: '6px 10px', fontFamily: 'inherit', fontSize: 14, width: 140 },
  btn: { background: '#21c074', color: '#04210f', border: 'none', borderRadius: 6, padding: '7px 14px', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
  current: { fontSize: 12, color: '#8b949e', marginLeft: 'auto' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 16 },
  panel: { background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: 14 },
  panelTitle: { fontSize: 13, color: '#8b949e', marginBottom: 10, textTransform: 'uppercase' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th: { textAlign: 'left', color: '#8b949e', borderBottom: '1px solid #30363d', padding: '4px 6px' },
  td: { padding: '4px 6px', borderBottom: '1px solid #21262d' },
  pnl: { fontSize: 32, fontWeight: 700 },
  sub: { fontSize: 12, color: '#8b949e', marginTop: 4 },
};
