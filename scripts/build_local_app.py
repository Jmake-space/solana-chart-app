#!/usr/bin/env python3
"""Generate ~/workspace/solana/app/index.html — self-contained chart app.
No external dependencies, no network calls at render time: all data is
embedded inline from chart-data.json (built from the local CSVs).
Vanilla canvas: candlestick/line, wheel-zoom, drag-pan, hover crosshair,
volume bars, timeframe selector, summary stats, forecast panel.
"""
import json
from pathlib import Path

BASE = Path.home() / "workspace/solana"
data = json.loads((BASE / "chart-data.json").read_text())
data_json = json.dumps(data, separators=(",", ":"))

html = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SOL Chart — Local Dataset</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
header{padding:16px 20px 8px}h1{font-size:20px;margin:0}h1 span{color:#9945ff}
.sub{color:#9aa0a6;font-size:13px;margin-top:4px}
.controls{display:flex;flex-wrap:wrap;gap:8px;padding:8px 20px;align-items:center}
.controls button{background:#1c1f26;color:#e6e6e6;border:1px solid #333842;border-radius:8px;padding:7px 12px;cursor:pointer;font-size:13px}
.controls button.active{background:#9945ff;border-color:#9945ff;color:#fff}
.controls button:hover{border-color:#9945ff}
.stats{display:flex;flex-wrap:wrap;gap:16px;padding:4px 20px 12px;font-size:13px;color:#c9cdd3}
.stats b{color:#fff;font-size:15px}.neg{color:#f6465d}.pos{color:#0ecb81}
#wrap{position:relative;margin:0 20px;background:#14161c;border:1px solid #262a33;border-radius:12px;overflow:hidden}
canvas{display:block;width:100%;height:520px;cursor:crosshair;touch-action:none}
#tip{position:absolute;pointer-events:none;background:rgba(20,22,28,.95);border:1px solid #333842;border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.5;display:none;white-space:nowrap;z-index:2}
#tip b{color:#fff}
section{margin:16px 20px;background:#14161c;border:1px solid #262a33;border-radius:12px;padding:16px 18px}
section h2{font-size:16px;margin:0 0 8px}section p,section li{font-size:13px;color:#c9cdd3;line-height:1.55}
table{border-collapse:collapse;font-size:13px;margin:8px 0}th,td{padding:6px 12px 6px 0;text-align:left;border-bottom:1px solid #262a33}th{color:#9aa0a6;font-weight:600}
.warn{background:#2a1f0d;border:1px solid #6b4d12;color:#f5c86b;border-radius:8px;padding:10px 12px;font-size:13px;margin:8px 0}
footer{padding:8px 20px 24px;color:#7a8089;font-size:12px}
</style></head><body>
<header><h1>SOL / USDT <span>— local chart</span></h1>
<div class="sub" id="meta"></div></header>
<div class="controls" id="tf">
<button data-tf="1D">1D</button><button data-tf="1W">1W</button><button data-tf="1M">1M</button>
<button data-tf="3M">3M</button><button data-tf="6M">6M</button><button data-tf="12M" class="active">12M</button><button data-tf="All">All</button><button data-tf="3Y">3Y weekly</button>
<span style="width:12px"></span>
<button id="modeCandle" class="active">Candlestick</button><button id="modeLine">Line</button>
<span style="width:12px"></span>
<button id="reset">Reset zoom</button><button id="clearSel">Clear selection</button>
<span style="color:#9aa0a6;font-size:12px">Drag to pan &middot; scroll to zoom &middot; hover or tap a candle for OHLC &middot; tap again or Clear selection to close</span>
</div>
<div class="stats" id="stats"></div>
<div id="wrap"><canvas id="c"></canvas><div id="tip"></div></div>
<section id="forecast"><h2>Forecast — experimental baseline, not financial advice</h2></section>
<section id="macro"><h2>3-year weekly view — macro context, not a forecast</h2></section>
<section><h2>About this data</h2>
<p>Source: Binance public market data (<code>data-api.binance.vision</code>), SOLUSDT, 1-hour candles, no API key.
8,783 closed hourly candles, 2025-11-17 00:00 UTC → 2026-11-17 22:00 UTC, plus a 366-row daily aggregate.
Verified on disk: 0 duplicate timestamps, 0 gaps, 0 OHLC violations; 3/3 spot-check closes match Binance live.
Full manifest: <code>~/workspace/solana/dataset/README.md</code>. No live calls at render time — everything on this page is embedded from the local CSVs.</p></section>
<footer>Local only. No trading, no orders, no wallet actions. Refresh: <code>scripts/fetch_binance.py</code> → <code>verify_dataset.py</code> → <code>forecast_v3.py</code> → <code>make_chart_data.py</code></footer>
<script>
const DATA = __DATA__;
const H = DATA.hourly, D = DATA.daily, F = DATA.forecast, WK = DATA.weekly || [], M = DATA.macro || {};
document.getElementById('meta').textContent =
  `Binance SOLUSDT · ${DATA.hourly_rows.toLocaleString()} hourly candles · ${DATA.first} → ${DATA.last} (UTC) · last close $${D[D.length-1][4].toFixed(2)}`;
// ---- forecast panel (v3 structure; defensive if keys are missing) ----
(function(){
  const el = document.getElementById('forecast');
  const C = F.context || {};
  const W = (F.backtest && F.backtest.windows) || {};
  const grid = F.vol_alpha_grid || {};
  const wrow = (name,v)=>`<tr><td>${name}</td><td>$${v.mae_usd}</td><td>${v.mae_pct}%</td><td>$${v.rmse_usd}</td><td>${v.directional_accuracy_pct===null?'n/a':v.directional_accuracy_pct+'%'}</td><td>${v.n}</td></tr>`;
  const reg = W.full_year_from_day_31 && W.full_year_from_day_31.per_regime;
  const regRows = reg ? Object.entries(reg).map(([r,v])=>`<tr><td>${r}</td><td>$${v.mae_usd}</td><td>${v.n}</td><td>${v.directional_accuracy_pct===null?'n/a':v.directional_accuracy_pct+'%'}</td></tr>`).join('') : '';
  const gridRows = Object.entries(grid).map(([a,g])=>`<tr><td>${a}</td><td>$${g.last_30d.mae_usd}</td><td>$${g.last_90d.mae_usd}</td><td>$${g.full_year.mae_usd}</td></tr>`).join('');
  el.innerHTML += `<div class="warn"><b>Experimental — not financial advice.</b> ${F.description || ''} <b>Honest reading:</b> no drift variant beats naive on MAE over 90 days or the full year (naive $2.33 / $2.17 vs v3 $2.37 / $2.21); v3 is a small, principled tilt, not a breakthrough.</div>
  <p>Context: last close $${F.inputs.last_close_usd} · MA7 $${C.ma7_usd} · MA30 $${C.ma30_usd} · drift30 ${C.drift_30d_pct_per_day}%/day · vol30 ${C.vol30_pct}% (${C.regime} regime) · vol7 ${C.vol7_pct}% · ATR14 ${C.atr14_pct}% · volume ratio ${C.volume_ratio_30d}&times; · vol-damp &times;${C.vol_damp}</p>
  <table><tr><th>Horizon</th><th>Date</th><th>Forecast</th><th>~95% band</th></tr>${F.forecast.map(f=>`<tr><td>+${f.horizon_days}d</td><td>${f.date}</td><td><b>$${f.forecast_close_usd}</b></td><td>$${f.low_95_usd} – $${f.high_95_usd}</td></tr>`).join('')}</table>
  <table><tr><th>Backtest window</th><th>MAE</th><th>MAE %</th><th>RMSE</th><th>Direction</th><th>n</th></tr>${Object.entries(W).map(([n,v])=>wrow(n,v)).join('')}</table>
  ${gridRows?`<table><tr><th>VOL_ALPHA</th><th>30d MAE</th><th>90d MAE</th><th>Full-year MAE</th></tr>${gridRows}</table><p style="font-size:12px;color:#9aa0a6">VOL_ALPHA is tunable in <code>config.json</code> (default 1.0; 0 = v2 exactly). Damping trims only ~1% MAE.</p>`:''}
  ${regRows?`<table><tr><th>Vol regime (full year)</th><th>MAE</th><th>n</th><th>Direction</th></tr>${regRows}</table>`:''}
  <p><b>Limits:</b></p><ul>${(F.limits||[]).map(l=>`<li>${l}</li>`).join('')}</ul>
  <p>Model: <code>${F.model||''}</code> · doc <code>models/baseline_v3.md</code> · config <code>config.json</code> · code <code>scripts/forecast_v3.py</code> (v1/v2 kept intact for comparison).</p>`;
})();
// ---- macro panel (3-year weekly; defensive if keys are missing) ----
(function(){
  const el = document.getElementById('macro');
  if(!M.weekly_rows || !WK.length){ el.innerHTML += '<p>Weekly data not in this build yet — re-run <code>scripts/make_chart_data.py</code>.</p>'; return; }
  const f4 = M.fwd4w || {}, f8 = M.fwd8w || {};
  el.innerHTML += `<div class="warn"><b>$69.70 is not a floor.</b> It is a v3 artefact: the drift is damped by 0.85^(h-1), so the point forecast mathematically flattens near $70. There is no weekly price structure at $69.70 — no cluster of closes, no prior low.</div>
  <p>${M.weekly_rows} weekly candles, ${M.first_week} → ${M.last_week} · last weekly close <b>$${M.last_weekly_close_usd}</b> · ATH close $${M.ath_close_usd} (high $${M.ath_high_usd}), ${M.drawdown_from_ath_close_pct}% from ATH close · 50-week MA $${M.ma50w_usd} (price ${((M.last_weekly_close_usd/M.ma50w_usd-1)*100).toFixed(1)}% below it) · 100-week MA $${M.ma100w_usd} · weekly RSI-14 ${M.weekly_rsi14} — not oversold on the weekly, even though the daily was. Only ${M.weeks_below_70_close} weeks in 3 years closed below $70.</p>
  <p><b>Levels to watch:</b> above — $${(M.levels_above_usd||[]).join(', $')}; below — $${(M.levels_below_usd||[]).join(', $')} (June 2026 trough close $66.50, then $59–60, then $51–53).</p>
  <table><tr><th>After a −20% month (n=${M.analogues_n})</th><th>Median</th><th>Positive</th><th>&gt; +33%</th><th>&lt; −20%</th></tr>
  <tr><td>+4 weeks</td><td>${f4.median_pct}%</td><td>${f4.positive}</td><td>${f4.gt_plus33pct}</td><td>${f4.lt_minus20pct}</td></tr>
  <tr><td>+8 weeks</td><td>${f8.median_pct}%</td><td>${f8.positive}</td><td>${f8.gt_plus33pct}</td><td>${f8.lt_minus20pct}</td></tr></table>
  <p><b>Back to $100</b> needs +${M.back_to_100_pct_needed}% — ${M.back_to_100_probability}. A further −20% leg is about as likely as the +33% recovery over the next month. <b>Nov–Dec:</b> ${M.nov_dec_read}</p>
  <p style="font-size:12px;color:#9aa0a6">Limits: 3 years / 160 weeks is thin; analogue n=21 with overlapping episodes. Weekly data says nothing about catalysts — price history only. Full write-up: <code>macro_3y_note.md</code> · data: <code>dataset/weekly/sol_ohlcv_weekly.csv</code>. Use the <b>3Y weekly</b> button above to chart these candles (tap a candle for its OHLC, as usual).</p>`;
})();
// ---- chart ----
const cv = document.getElementById('c'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
let tf='12M', mode='candle', view=null, hover=-1;
function series(){
  if(tf==='3Y') return WK;
  if(tf==='1D') return H.slice(-24);
  if(tf==='1W') return H.slice(-168);
  const n = tf==='1M'?30: tf==='3M'?90: tf==='6M'?182: D.length;
  return D.slice(-n);
}
function resetView(){ const s=series(); view={start:0, end:s.length}; hover=-1; draw(); updateStats(); }
function updateStats(){
  const s=series().slice(view.start, view.end);
  const closes=s.map(r=>r[4]), hi=Math.max(...s.map(r=>r[2])), lo=Math.min(...s.map(r=>r[3]));
  const first=s[0][4], last=s[s.length-1][4], ch=(last/first-1)*100;
  document.getElementById('stats').innerHTML =
    `<span>Last price <b>$${last.toFixed(2)}</b> <span style="color:#9aa0a6">as of ${new Date(s[s.length-1][0]).toISOString().slice(0,16).replace('T',' ')} UTC</span></span>
     <span>Period high <b>$${hi.toFixed(2)}</b></span><span>Period low <b>$${lo.toFixed(2)}</b></span>
     <span>Change <b class="${ch>=0?'pos':'neg'}">${ch>=0?'+':''}${ch.toFixed(2)}%</b></span>
     <span>Candles <b>${s.length}</b> (${tf==='3Y'?'weekly':tf==='1D'||tf==='1W'?'hourly':'daily'})</span>`;
}
function draw(){
  const W=cv.clientWidth, Hh=cv.clientHeight, dpr=window.devicePixelRatio||1;
  if(cv.width!==W*dpr){cv.width=W*dpr; cv.height=Hh*dpr;}
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,W,Hh);
  const s=series(), vis=s.slice(view.start, view.end);
  if(!vis.length) return;
  const padR=64, padT=12, padB=18, volH=Hh*0.18, chartH=Hh-padT-padB-volH-8;
  let hi=Math.max(...vis.map(r=>r[2])), lo=Math.min(...vis.map(r=>r[3]));
  const pad=(hi-lo)*0.04||1; hi+=pad; lo-=pad;
  const maxV=Math.max(...vis.map(r=>r[5]));
  const x=i=> (i+0.5)*(W-padR)/vis.length;
  const y=p=>(padT+(hi-p)/(hi-lo)*chartH);
  const yv=v=> padT+chartH+8+(1-v/maxV)*volH;
  // grid + price labels
  ctx.strokeStyle='#23272f'; ctx.fillStyle='#9aa0a6'; ctx.font='11px sans-serif'; ctx.textAlign='left';
  for(let g=0;g<=4;g++){ const p=lo+(hi-lo)*g/4, yy=y(p);
    ctx.beginPath(); ctx.moveTo(0,yy); ctx.lineTo(W-padR,yy); ctx.stroke();
    ctx.fillText('$'+p.toFixed(p<10?2:0), W-padR+6, yy+4); }
  // volume
  vis.forEach((r,i)=>{ ctx.fillStyle = r[4]>=r[1] ? 'rgba(14,203,129,.45)':'rgba(246,70,93,.45)';
    ctx.fillRect(x(i)-Math.max(1,(W-padR)/vis.length*0.6)/2, yv(r[5]), Math.max(1,(W-padR)/vis.length*0.6), padT+chartH+8+volH-yv(r[5])); });
  if(mode==='candle'){
    const bw=Math.max(1,(W-padR)/vis.length*0.7);
    vis.forEach((r,i)=>{ const up=r[4]>=r[1], col=up?'#0ecb81':'#f6465d';
      ctx.strokeStyle=col; ctx.fillStyle=col;
      ctx.beginPath(); ctx.moveTo(x(i),y(r[2])); ctx.lineTo(x(i),y(r[3])); ctx.stroke();
      const t=y(Math.max(r[1],r[4])), b=y(Math.min(r[1],r[4]));
      ctx.fillRect(x(i)-bw/2, t, bw, Math.max(1,b-t)); });
  } else {
    ctx.beginPath();
    vis.forEach((r,i)=>{ const xx=x(i), yy=y(r[4]); i?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy); });
    ctx.strokeStyle='#9945ff'; ctx.lineWidth=2; ctx.stroke();
    ctx.lineTo(x(vis.length-1), padT+chartH); ctx.lineTo(x(0), padT+chartH); ctx.closePath();
    ctx.fillStyle='rgba(153,69,255,.12)'; ctx.fill();
  }
  // MA7 / MA30 on daily series only (not hourly, not weekly)
  if(!(tf==='1D'||tf==='1W'||tf==='3Y')){
    [[7,'#f0b90b'],[30,'#00c4ff']].forEach(([n,col])=>{
      ctx.beginPath(); let started=false;
      vis.forEach((r,i)=>{ const gi=view.start+i; if(gi<n-1) return;
        const m=s.slice(gi-n+1,gi+1).reduce((a,b)=>a+b[4],0)/n;
        const xx=x(i), yy=y(m); started?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy); started=true; });
      ctx.strokeStyle=col; ctx.lineWidth=1.2; ctx.stroke(); });
    ctx.fillStyle='#9aa0a6'; ctx.fillText('— MA7 (yellow)  — MA30 (blue)', 8, Hh-4);
  }
  // hover crosshair
  if(hover>=0 && hover<vis.length){
    const r=vis[hover], xx=x(hover);
    ctx.strokeStyle='rgba(230,230,230,.5)'; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(xx,padT); ctx.lineTo(xx,padT+chartH+8+volH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0,y(r[4])); ctx.lineTo(W-padR,y(r[4])); ctx.stroke(); ctx.setLineDash([]);
  }
  // x labels
  ctx.fillStyle='#9aa0a6';
  const step=Math.ceil(vis.length/6);
  for(let i=0;i<vis.length;i+=step){ const d=new Date(vis[i][0]);
    ctx.fillText(tf==='1D'||tf==='1W' ? d.toISOString().slice(5,16).replace('T',' ') : d.toISOString().slice(0,10), x(i)-20, Hh-4); }
}
function showTip(e){
  const rect=cv.getBoundingClientRect(), s=series(), vis=s.slice(view.start, view.end);
  const i=Math.floor((e.clientX-rect.left)/(rect.width-64)*vis.length);
  if(i<0||i>=vis.length){ tip.style.display='none'; hover=-1; draw(); return; }
  hover=i; const r=vis[i], d=new Date(r[0]).toISOString().replace('T',' ').slice(0,16)+' UTC';
  const up=r[4]>=r[1];
  tip.innerHTML=`<b>${d}</b><br>O $${r[1].toFixed(2)} &nbsp; H $${r[2].toFixed(2)}<br>L $${r[3].toFixed(2)} &nbsp; C <b style="color:${up?'#0ecb81':'#f6465d'}">$${r[4].toFixed(2)}</b><br>Vol ${r[5].toLocaleString(undefined,{maximumFractionDigits:0})} SOL`;
  tip.style.display='block';
  tip.style.left=Math.min(e.clientX-rect.left+14, rect.width-190)+'px';
  tip.style.top=Math.max(e.clientY-rect.top-10, 4)+'px';
  draw();
}
document.getElementById('tf').addEventListener('click', e=>{
  const b=e.target.closest('button[data-tf]'); if(!b) return;
  document.querySelectorAll('#tf button[data-tf]').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); tf=b.dataset.tf; resetView();
});
document.getElementById('modeCandle').onclick=()=>{mode='candle';document.getElementById('modeCandle').classList.add('active');document.getElementById('modeLine').classList.remove('active');draw();};
document.getElementById('modeLine').onclick=()=>{mode='line';document.getElementById('modeLine').classList.add('active');document.getElementById('modeCandle').classList.remove('active');draw();};
document.getElementById('reset').onclick=resetView;
document.getElementById('clearSel').onclick=()=>{tip.style.display='none'; hover=-1; draw();};
let drag=null;
cv.addEventListener('mousedown', e=>{drag={x:e.clientX, start:view.start, end:view.end};});
window.addEventListener('mouseup', ()=>drag=null);
window.addEventListener('mousemove', e=>{ if(!drag) return;
  const s=series(), span=view.end-view.start, dx=Math.round((drag.x-e.clientX)/cv.clientWidth*span);
  let ns=Math.max(0,Math.min(s.length-span, drag.start+dx));
  view={start:ns, end:ns+span}; draw(); updateStats(); });
cv.addEventListener('wheel', e=>{ e.preventDefault();
  const s=series(), span=view.end-view.start, rect=cv.getBoundingClientRect();
  const frac=(e.clientX-rect.left)/(rect.width-64), centre=view.start+frac*span;
  const ns2=Math.max(10, Math.min(s.length, Math.round(span*(e.deltaY>0?1.15:0.87))));
  let ns=Math.round(centre-frac*ns2); ns=Math.max(0,Math.min(s.length-ns2, ns));
  view={start:ns, end:ns+ns2}; draw(); updateStats(); }, {passive:false});
cv.addEventListener('mousemove', showTip);
cv.addEventListener('mouseleave', ()=>{tip.style.display='none'; hover=-1; draw();});
// touch: tap a candle to pin its OHLC (stays visible); drag with one finger to pan
let touchStart=null;
cv.addEventListener('touchstart', e=>{ e.preventDefault(); const t=e.touches[0];
  // tap the already-pinned candle again to close the overlay (no reset needed)
  const rect=cv.getBoundingClientRect(), s=series(), vis=s.slice(view.start, view.end);
  const i=Math.floor((t.clientX-rect.left)/(rect.width-64)*vis.length);
  if(i===hover && tip.style.display==='block'){ tip.style.display='none'; hover=-1; draw(); touchStart=null; return; }
  touchStart={x:t.clientX, start:view.start, end:view.end};
  showTip({clientX:t.clientX, clientY:t.clientY}); }, {passive:false});
cv.addEventListener('touchmove', e=>{ e.preventDefault(); if(!touchStart) return; const t=e.touches[0];
  const s=series(), span=view.end-view.start;
  const dx=Math.round((touchStart.x-t.clientX)/cv.clientWidth*span);
  if(Math.abs(t.clientX-touchStart.x)>12){ tip.style.display='none'; hover=-1;
    const ns=Math.max(0,Math.min(s.length-span, touchStart.start+dx));
    view={start:ns, end:ns+span}; draw(); updateStats(); }
  else showTip({clientX:t.clientX, clientY:t.clientY}); }, {passive:false});
cv.addEventListener('touchend', ()=>{ touchStart=null; /* tip stays pinned after a tap */ });
window.addEventListener('resize', draw);
resetView();
</script></body></html>
"""

html = html.replace("__DATA__", data_json)
out = BASE / "app" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size:,} bytes)")
