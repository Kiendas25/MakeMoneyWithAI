// Self-contained INTERACTIVE preview generator. Produces a single HTML file
// (no server, no network) where you type the per-trade montante (USD) and the
// page recomputes opportunities, net bps and paper PnL in the browser. Built for
// mobile: open the file and it just works.
//
// The recompute JS embedded below mirrors the TS source of truth
// (models/slippage.ts + models/arbitrage.ts). Keep them in sync; the engine and
// backtester remain the authoritative path — this is a portable demo artifact.

import { writeFileSync } from 'node:fs';
import { makePair, type Quote } from '../exchange/types.js';

export interface PreviewSnapshot {
  universe: string[];
  quotes: Quote[];
  defaultNotionalUsd: number;
  minEdgeBps: number;
  source: string; // "synthetic" | "live snapshot (N ticks)"
}

// ---- synthetic snapshot (deterministic) ----------------------------------
const VENUES = ['jupiter', 'orca', 'raydium', 'binance', 'coinbase'] as const;
const SYNTH_PAIRS = ['SOL/USDC', 'SOL/USDT', 'JUP/USDC', 'JTO/USDC', 'BONK/USDC', 'WIF/USDC'];
const REF: Record<string, number> = {
  'SOL/USDC': 152.4, 'SOL/USDT': 152.5, 'JUP/USDC': 0.84,
  'JTO/USDC': 2.91, 'BONK/USDC': 0.0000231, 'WIF/USDC': 1.73,
};

export function syntheticSnapshot(defaultNotionalUsd = 10_000, minEdgeBps = 3): PreviewSnapshot {
  let seed = 0x9e3779b9;
  const rng = () => {
    seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5;
    return ((seed >>> 0) % 1_000_000) / 1_000_000;
  };
  const now = Date.now();
  const quotes: Quote[] = [];
  for (const key of SYNTH_PAIRS) {
    const [base, quote] = key.split('/') as [string, string];
    const pair = makePair(base, quote);
    const ref = REF[key]!;
    for (const venue of VENUES) {
      const drift = (rng() - 0.5) * 0.006; // ±30bps dispersion
      const mid = ref * (1 + drift);
      const half = mid * 0.0003;
      quotes.push({
        venue,
        kind: venue === 'binance' || venue === 'coinbase' ? 'cex' : 'dex',
        pair, bid: mid - half, ask: mid + half, mid,
        feeBps: venue === 'jupiter' ? 0 : venue === 'coinbase' ? 40 : venue === 'binance' ? 10 : 25,
        executable: venue === 'jupiter', ts: now, latencyMs: 30 + rng() * 60, stale: false,
      });
    }
  }
  return { universe: SYNTH_PAIRS, quotes, defaultNotionalUsd, minEdgeBps, source: 'synthetic' };
}

// ---- HTML builder ---------------------------------------------------------
export function buildPreviewHtml(snap: PreviewSnapshot): string {
  const data = JSON.stringify({
    universe: snap.universe,
    quotes: snap.quotes,
    defaultNotional: snap.defaultNotionalUsd,
    minEdgeBps: snap.minEdgeBps,
    source: snap.source,
  });

  return `<!doctype html><html lang="pt"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Quantum-Arb-SOL — preview interativo</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0d1117;color:#e6edf3;padding:16px}
.head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}h1{font-size:18px;margin:0}
.tag{font-size:11px;color:#8b949e}.dot{width:10px;height:10px;border-radius:50%;background:#21c074;margin-left:auto}
.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0;padding:12px;background:#161b22;border:1px solid #30363d;border-radius:8px}
label{font-size:13px;color:#8b949e}
input{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:8px 10px;font-family:inherit;font-size:16px;width:130px}
.metrics{font-size:12px;color:#8b949e;margin:12px 0;line-height:1.6}
.grid{display:grid;grid-template-columns:1fr;gap:14px}
.panel{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px}
.ptitle{font-size:12px;color:#8b949e;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#8b949e;border-bottom:1px solid #30363d;padding:5px 6px;font-weight:600}
td{padding:5px 6px;border-bottom:1px solid #21262d}
.pos{color:#21c074;font-weight:700}.neg{color:#c0392b}
.pnl{font-size:34px;font-weight:800}.sub{font-size:12px;color:#8b949e;margin-top:4px}
.banner{font-size:11px;color:#8b949e;margin-top:18px;border-top:1px solid #21262d;padding-top:10px}
</style></head><body>
<div class="head"><h1>Quantum-Arb-SOL</h1><span class="tag">simulação · paper-trade — sem execução real</span><span class="dot"></span></div>
<div class="controls">
  <label>Montante por trade (USD)</label>
  <input id="notional" type="number" min="1" step="100" inputmode="decimal">
  <label>Min edge (bps)</label>
  <input id="minedge" type="number" min="0" step="1" style="width:90px">
</div>
<div class="metrics" id="metrics"></div>
<div class="grid">
  <div class="panel"><div class="ptitle">Spreads por par</div>
    <table><thead><tr><th>Par</th><th>Best bid</th><th>Best ask</th><th>Venues</th></tr></thead><tbody id="spreads"></tbody></table></div>
  <div class="panel"><div class="ptitle">Oportunidades (net bps)</div>
    <table><thead><tr><th>Par</th><th>Buy</th><th>Sell</th><th>Net bps</th></tr></thead><tbody id="opps"></tbody></table></div>
  <div class="panel"><div class="ptitle">Paper PnL</div>
    <div class="pnl" id="pnl">$0.00</div><div class="sub" id="pnlsub"></div></div>
</div>
<div class="banner" id="banner"></div>
<script>
const SNAP = ${data};
// Mirrors models/slippage.ts DEFAULTS.
const SLIP = {
  jupiter:{kLin:0,kSqrt:0,refNotional:1}, orca:{kLin:1.5,kSqrt:8,refNotional:1e4},
  raydium:{kLin:2,kSqrt:10,refNotional:1e4}, binance:{kLin:.5,kSqrt:3,refNotional:1e4},
  coinbase:{kLin:.8,kSqrt:4,refNotional:1e4}
};
const GAS = {jupiter:1,orca:1,raydium:1};
function paramBps(p,n){const q=n/p.refNotional;return p.kLin*q+p.kSqrt*Math.sqrt(q);}
function walkBps(q,side,n){
  const book=q.book,levels=side==='buy'?book.asks:book.bids,top=side==='buy'?q.ask:q.bid;
  let rem=n,base=0,spent=0;
  for(const l of levels){const ln=l.px*l.sz,take=Math.min(rem,ln);base+=take/l.px;spent+=take;rem-=take;if(rem<=1e-9)break;}
  if(base<=0)return paramBps(SLIP[q.venue],n);
  const avg=spent/base;let bps=Math.abs(avg-top)/top*1e4;
  if(rem>1e-9)bps+=paramBps(SLIP[q.venue],rem);
  return bps;
}
function slipBps(q,side,n){
  if(q.executable)return 0;if(n<=0)return 0;
  if(q.book&&(side==='buy'?q.book.asks.length:q.book.bids.length))return walkBps(q,side,n);
  return paramBps(SLIP[q.venue],n);
}
function detect(quotes,notional,minEdge){
  const byPair={};
  for(const q of quotes){(byPair[q.pair.key]=byPair[q.pair.key]||[]).push(q);}
  const out=[];
  for(const key in byPair){
    const fresh=byPair[key].filter(q=>!q.stale);if(fresh.length<2)continue;
    let best=null;
    for(const buy of fresh)for(const sell of fresh){
      if(buy.venue===sell.venue)continue;
      const gross=(sell.bid-buy.ask)/buy.ask*1e4;
      const fee=buy.feeBps+sell.feeBps;
      const slip=slipBps(buy,'buy',notional)+slipBps(sell,'sell',notional);
      const gas=(GAS[buy.venue]||0)+(GAS[sell.venue]||0);
      const net=gross-fee-slip-gas;
      if(net>=minEdge&&(!best||net>best.netBps))
        best={pair:buy.pair,buyVenue:buy.venue,sellVenue:sell.venue,grossBps:gross,feeBps:fee,slipBps:slip,gasBps:gas,netBps:net};
    }
    if(best)out.push(best);
  }
  out.sort((a,b)=>a.pair.key<b.pair.key?-1:a.pair.key>b.pair.key?1:0);
  return out;
}
const fmt=n=>n<0.01?n.toExponential(3):n.toFixed(4);
function render(){
  const notional=Math.max(1,Number(document.getElementById('notional').value)||0);
  const minEdge=Math.max(0,Number(document.getElementById('minedge').value)||0);
  // spreads
  let srows='';
  for(const key of SNAP.universe){
    const qs=SNAP.quotes.filter(q=>q.pair.key===key);
    const bb=Math.max(...qs.map(q=>q.bid)),ba=Math.min(...qs.map(q=>q.ask));
    srows+='<tr><td>'+key+'</td><td>'+fmt(bb)+'</td><td>'+fmt(ba)+'</td><td>'+qs.length+'</td></tr>';
  }
  document.getElementById('spreads').innerHTML=srows;
  // opps + pnl
  const opps=detect(SNAP.quotes,notional,minEdge);
  let orows='',pnl=0;
  for(const o of opps){
    pnl+=notional*o.netBps/1e4;
    orows+='<tr><td>'+o.pair.key+'</td><td>'+o.buyVenue+'</td><td>'+o.sellVenue+'</td><td class="'+(o.netBps>0?'pos':'neg')+'">'+o.netBps.toFixed(2)+'</td></tr>';
  }
  if(!opps.length)orows='<tr><td colspan="4" style="color:#8b949e">nenhuma oportunidade ≥ '+minEdge+'bps</td></tr>';
  document.getElementById('opps').innerHTML=orows;
  document.getElementById('pnl').textContent='$'+pnl.toFixed(2);
  document.getElementById('pnl').className='pnl '+(pnl>=0?'pos':'neg');
  document.getElementById('pnlsub').textContent=opps.length+' fills · montante $'+notional.toLocaleString();
  document.getElementById('metrics').innerHTML='quotes '+SNAP.quotes.length+' · venues 5 · pares '+SNAP.universe.length+
    '<br>universe (present in all venues): '+SNAP.universe.join(' · ');
  document.getElementById('banner').textContent='Preview interativo ('+SNAP.source+'). Recálculo no browser espelha models/slippage.ts + models/arbitrage.ts. Muda o montante para ver net bps e PnL a reagir.';
}
document.getElementById('notional').value=SNAP.defaultNotional;
document.getElementById('minedge').value=SNAP.minEdgeBps;
document.getElementById('notional').addEventListener('input',render);
document.getElementById('minedge').addEventListener('input',render);
render();
</script></body></html>`;
}

// ---- direct invocation: write a synthetic interactive preview -------------
const invokedDirectly = process.argv[1]?.endsWith('preview.ts') || process.argv[1]?.endsWith('preview.js');
if (invokedDirectly) {
  const out = process.argv[2] ?? 'quantum-arb-preview.html';
  const html = buildPreviewHtml(syntheticSnapshot());
  writeFileSync(out, html);
  console.log(`wrote ${out} (synthetic, interactive)`);
}
