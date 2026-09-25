#!/usr/bin/env python3
"""Stage 4: render layout.json into one self-contained interactive HTML.

No CDN, no server, no build step. Canvas 2D handles a few thousand nodes fine
and keeps the output a single portable file.

Output: method_galaxy.html
"""
import json
import os

WORK = os.path.abspath(os.environ.get("MGAL_WORK", "./work"))
OUT = os.path.abspath(os.environ.get("MGAL_OUT", "./method_galaxy.html"))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DH Method Galaxy — ETKAD in European digital humanities</title>
<style>
  :root{--bg:#06070d;--fg:#e9edf6;--dim:#8590a8;--line:#1d2333;--acc:#6fd3e8;
        --ee:#ff5c8a;--panel:#0a0d16;}
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);
    font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  #wrap{display:flex;height:100%}
  #rail{width:232px;border-right:1px solid var(--line);background:var(--panel);
    overflow-y:auto;padding:14px 13px;flex-shrink:0}
  #stage{flex:1;position:relative;min-width:0}
  canvas{display:block;width:100%;height:100%;cursor:grab}
  canvas.drag{cursor:grabbing}
  #side{width:370px;border-left:1px solid var(--line);background:var(--panel);
    overflow-y:auto;padding:18px;flex-shrink:0}
  h4{font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);
    margin:16px 0 7px;font-weight:600}
  h4:first-child{margin-top:0}
  .seg{display:flex;gap:0;border:1px solid var(--line);border-radius:7px;overflow:hidden}
  .seg button{flex:1;background:transparent;border:0;color:var(--dim);padding:6px 4px;
    font:inherit;font-size:11.5px;cursor:pointer}
  .seg button.on{background:var(--acc);color:#04121a;font-weight:600}
  .seg button:hover:not(.on){background:#141a28;color:var(--fg)}
  select,input[type=text]{width:100%;background:#111726;color:var(--fg);
    border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit;font-size:12px}
  input[type=text]:focus,select:focus{outline:none;border-color:var(--acc)}
  label.ck{display:flex;align-items:center;gap:7px;padding:3px 0;font-size:12px;cursor:pointer;color:#c2cade}
  label.ck:hover{color:var(--fg)}
  input[type=range]{width:100%}
  .btn{width:100%;background:#131a29;color:var(--fg);border:1px solid var(--line);
    border-radius:6px;padding:7px;font:inherit;font-size:12px;cursor:pointer;margin-top:6px}
  .btn:hover{border-color:var(--acc);color:var(--acc)}
  .btn.act{border-color:var(--ee);color:var(--ee)}
  #tip{position:absolute;pointer-events:none;background:rgba(8,11,19,.97);
    border:1px solid var(--line);border-radius:7px;padding:6px 10px;font-size:12px;
    display:none;z-index:9;max-width:340px}
  #foot{position:absolute;bottom:10px;left:14px;color:var(--dim);font-size:11px}
  #hint{position:absolute;bottom:10px;right:14px;color:var(--dim);font-size:11px}
  #lgd{position:absolute;top:12px;right:14px;font-size:11px;text-align:right;
    background:rgba(8,11,19,.82);padding:8px 11px;border-radius:8px;border:1px solid var(--line)}
  #lgd div{margin:2px 0;color:#c2cade}
  #lgd i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
  a{color:var(--acc);text-decoration:none} a:hover{text-decoration:underline}
  .chip{display:inline-block;background:#141b2b;border:1px solid var(--line);
    border-radius:20px;padding:3px 10px;margin:0 4px 5px 0;cursor:pointer;font-size:11.5px}
  .chip:hover{border-color:var(--acc);color:var(--acc)}
  .chip.ee{border-color:var(--ee);color:var(--ee)}
  #side h2{margin:0 0 3px;font-size:18px;line-height:1.25}
  #side .sub{color:var(--dim);font-size:11.5px;margin-bottom:12px}
  #side p{margin:0 0 10px;color:#c3cbdd}
  .row{padding:6px 0;border-bottom:1px solid #131a29;font-size:12px}
  .row span{color:var(--dim);font-size:10.5px;display:block}
  .empty{color:var(--dim);font-style:italic}
  .bar{height:5px;border-radius:3px;background:#151b2b;margin:4px 0 10px;display:flex;overflow:hidden}
  .stage{border-left:2px solid var(--ee);padding:2px 0 2px 9px;margin:0 0 9px}
  .stage b{font-size:12px}
  table.gap{width:100%;border-collapse:collapse;font-size:11.5px}
  table.gap td{padding:3px 4px;border-bottom:1px solid #131a29}
  table.gap td.n{color:var(--dim);text-align:right;width:44px}
  .tl{position:relative;height:20px;margin:2px 0 9px;background:#111726;border-radius:4px}
  .tl i{position:absolute;top:3px;height:14px;border-radius:3px;opacity:.35}
  .tl b{position:absolute;top:1px;width:3px;height:18px;border-radius:2px}
  .tlx{display:flex;justify-content:space-between;color:var(--dim);font-size:10px;margin-top:-4px}
</style>
</head>
<body>
<div id="wrap">
  <div id="rail">
    <h4>Space</h4>
    <div class="seg" id="spaceSeg">
      <button data-v="method" class="on">Methods</button>
      <button data-v="item">Objects</button>
    </div>
    <h4>Distance</h4>
    <div class="seg" id="modeSeg"></div>
    <h4>Colour by</h4>
    <select id="colour"></select>
    <h4>Search</h4>
    <input type="text" id="q" placeholder="filter by name…" autocomplete="off">
    <h4>Filters</h4>
    <div id="filters"></div>
    <h4>Minimum size</h4>
    <input type="range" id="minN" min="1" max="30" value="1">
    <div class="sub" id="minNlab" style="color:var(--dim);font-size:11px"></div>
    <h4>Estonian workflows</h4>
    <div id="eeList"></div>
    <button class="btn" id="clearEE">Clear overlay</button>
    <h4>Views</h4>
    <button class="btn" id="gapBtn">Method gap report</button>
    <button class="btn" id="adjBtn">Adjacent opportunities</button>
    <button class="btn" id="shapeBtn">Shape of a workflow</button>
    <button class="btn" id="csvBtn">Download gap CSV</button>
    <button class="btn" id="reset">Reset view</button>
    <button class="btn" id="png">Export PNG</button>
    <button class="btn" id="link">Copy link to this view</button>
    <label class="ck"><input type="checkbox" id="lab" checked> Labels</label>
    <label class="ck"><input type="checkbox" id="edg" checked> Edges on focus</label>
    <label class="ck"><input type="checkbox" id="halo" checked> Highlight Estonian</label>
    <label class="ck"><input type="checkbox" id="dens"> Density field</label>
  </div>
  <div id="stage">
    <canvas id="cv"></canvas>
    <div id="tip"></div>
    <div id="lgd"></div>
    <div id="foot"></div>
    <div id="hint">scroll zoom · drag pan · click a dot</div>
  </div>
  <div id="side"></div>
</div>
<script>
const DATA = __DATA__;
const S = {
  space: 'method',
  mode: DATA.default_mode.method,
  colour: 'cluster',
  q: '', minN: 1,
  cats: new Set(Object.keys(DATA.stats.cats)),
  groups: null,      // null = all TaDiRAH goals; else a Set
  srcq: '', langq: '',
  sel: null, hover: null, ee: null,
  labels: true, edges: true, halo: true, dens: false,
};
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const tip = document.getElementById('tip'), side = document.getElementById('side');
let view = {s:1,tx:0,ty:0}, base = null;

/* ---------- palettes ---------- */
const GROUP_COL = {
  'Capture':'#4ade80','Creation':'#60a5fa','Enrichment':'#c084fc','Analysis':'#fbbf24',
  'Interpretation':'#f472b6','Storage':'#22d3ee','Dissemination':'#fb923c',
  'Discovery':'#a3e635','Other':'#8b95ab'};
const CAT_COL = {
  'tool-or-service':'#60a5fa','dataset':'#4ade80','training-material':'#fbbf24',
  'publication':'#c084fc','workflow':'#22d3ee','etkad-workflow':'#ff5c8a'};
const CAT_LAB = {
  'tool-or-service':'Tools & services','dataset':'Datasets',
  'training-material':'Training materials','publication':'Publications',
  'workflow':'Workflows (SSHOMP)','etkad-workflow':'ETKAD workflows'};
function clusterCol(c,a){ if(c<0) return `rgba(105,115,140,${a})`;
  return `hsla(${(c*47)%360},68%,63%,${a})`; }
function hexA(h,a){const n=parseInt(h.slice(1),16);
  return `rgba(${n>>16&255},${n>>8&255},${n&255},${a})`;}

/* ---------- current view data ---------- */
function cur(){
  const sp = DATA[S.space], L = sp.layouts[S.mode];
  return {nodes: sp.nodes, xy: L.xy, c: L.c, clusters: L.clusters};
}
const isMethod = () => S.space === 'method';
function nodeName(n){ return isMethod() ? n.id : n.label; }
function nodeSize(n){ return isMethod() ? n.n : n.na; }

/* ---------- colour selection ---------- */
const COLOUR_OPTS = {
  method: [['cluster','Cluster'],['group','TaDiRAH goal'],['ee','Used by ETKAD'],
           ['gap','Gap (Europe vs Estonia)']],
  item:   [['cluster','Cluster'],['cat','Object type'],['ee','ETKAD vs rest']],
};
function colourOf(n,i,a){
  const C = cur();
  switch(S.colour){
    case 'group': return hexA(GROUP_COL[n.group]||GROUP_COL.Other, a);
    case 'cat':   return hexA(CAT_COL[n.cat]||'#8b95ab', a);
    case 'ee':
      if(isMethod()) return n.etkad>0 ? hexA('#ff5c8a',a) : `rgba(90,100,124,${a*0.75})`;
      return n.origin==='etkad' ? hexA('#ff5c8a',a) : `rgba(96,165,250,${a*0.6})`;
    case 'gap': {
      const g = Math.max(0, Math.min(1, (n.gap||0)/0.25));
      return `hsla(${(1-g)*150},72%,${58-g*8}%,${a})`;
    }
    default: return clusterCol(C.c[i], a);
  }
}

/* ---------- filtering ---------- */
function visible(n,i){
  if(nodeSize(n) < S.minN) return false;
  if(isMethod() && S.groups && !S.groups.has(n.group)) return false;
  if(!isMethod() && !S.cats.has(n.cat)) return false;
  if(!isMethod() && S.srcq && !String(n.src||'').toLowerCase().includes(S.srcq)) return false;
  if(!isMethod() && S.langq &&
     !(n.langs||[]).some(l=>l.toLowerCase().includes(S.langq))) return false;
  if(S.q){
    const t = (nodeName(n)+' '+(n.desc||'')+' '+((n.acts||[]).join(' '))).toLowerCase();
    if(!t.includes(S.q)) return false;
  }
  return true;
}
/* Activities belonging to the currently overlaid ETKAD workflow */
function eeActs(){
  if(!S.ee) return null;
  const w = DATA.item.nodes.find(n=>n.id===S.ee);
  return w ? new Set(w.acts) : null;
}

/* ---------- view transform ---------- */
function pct(arr,p){const s=[...arr].sort((a,b)=>a-b);
  return s[Math.min(s.length-1,Math.max(0,Math.round(p*(s.length-1))))];}
function fit(keep){
  const dpr = window.devicePixelRatio||1, w=cv.clientWidth, h=cv.clientHeight;
  cv.width=w*dpr; cv.height=h*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  const C=cur(), xs=C.xy.map(p=>p[0]), ys=C.xy.map(p=>p[1]);
  const b={x0:pct(xs,.03),x1:pct(xs,.97),y0:pct(ys,.03),y1:pct(ys,.97)};
  const pad=70, sx=(w-pad*2)/((b.x1-b.x0)||1), sy=(h-pad*2)/((b.y1-b.y0)||1);
  const s=Math.min(sx,sy);
  base={s, tx:pad-b.x0*s+(w-pad*2-(b.x1-b.x0)*s)/2,
           ty:pad-b.y0*s+(h-pad*2-(b.y1-b.y0)*s)/2};
  if(!keep) view={...base};
  draw();
}
const PX=(i)=>cur().xy[i][0]*view.s+view.tx;
const PY=(i)=>cur().xy[i][1]*view.s+view.ty;
function rad(n){
  const C=cur(), mx = isMethod()?Math.max(...C.nodes.map(x=>x.n))
                              :Math.max(...C.nodes.map(x=>x.na));
  const z = Math.min(2.1, Math.max(.55, view.s/base.s));
  return Math.max(isMethod()?3.2:2.0, Math.sqrt(nodeSize(n)/mx)*(isMethod()?26:15))*z;
}

/* ---------- draw ---------- */
function draw(){
  const C=cur(), w=cv.clientWidth, h=cv.clientHeight;
  ctx.clearRect(0,0,w,h); ctx.fillStyle='#06070d'; ctx.fillRect(0,0,w,h);
  const idx = new Map(C.nodes.map((n,i)=>[n.id,i]));
  const focus = S.hover || S.sel;
  const ea = eeActs();

  /* density field — where is the corpus thick? Cheap additive blobs rather than
     a real KDE; the point is to see crowding, not to measure it. */
  if(S.dens){
    ctx.globalCompositeOperation='lighter';
    for(let i=0;i<C.nodes.length;i++){
      if(!visible(C.nodes[i],i)) continue;
      const X=PX(i),Y=PY(i); if(X<-60||X>w+60||Y<-60||Y>h+60) continue;
      const R=Math.max(26, rad(C.nodes[i])*5);
      const g=ctx.createRadialGradient(X,Y,0,X,Y,R);
      g.addColorStop(0,'rgba(70,140,190,.14)'); g.addColorStop(1,'rgba(70,140,190,0)');
      ctx.fillStyle=g; ctx.beginPath(); ctx.arc(X,Y,R,0,6.284); ctx.fill();
    }
    ctx.globalCompositeOperation='source-over';
  }

  /* ETKAD constellation: the selected workflow's stages as a path through
     method space. This is the whole point of the overlay — a workflow is a
     route, not a bag of tags. */
  if(isMethod() && S.ee){
    const w0 = DATA.item.nodes.find(n=>n.id===S.ee);
    if(w0 && w0.stages && w0.stages.length){
      const pts = w0.stages.map(st=>{
        const ids = st.acts.map(a=>idx.get(a)).filter(v=>v!==undefined);
        if(!ids.length) return null;
        return {x:ids.reduce((s,i)=>s+PX(i),0)/ids.length,
                y:ids.reduce((s,i)=>s+PY(i),0)/ids.length, t:st.title, ids};
      }).filter(Boolean);
      ctx.lineWidth=2; ctx.strokeStyle='rgba(255,92,138,.55)';
      ctx.setLineDash([6,4]); ctx.beginPath();
      pts.forEach((p,i)=> i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
      ctx.stroke(); ctx.setLineDash([]);
      pts.forEach((p,i)=>{
        ctx.beginPath(); ctx.arc(p.x,p.y,11,0,6.284);
        ctx.fillStyle='rgba(255,92,138,.9)'; ctx.fill();
        ctx.fillStyle='#0b0510'; ctx.font='700 11px sans-serif';
        ctx.textAlign='center'; ctx.textBaseline='middle';
        ctx.fillText(String(i+1), p.x, p.y+.5);
      });
      ctx.textBaseline='alphabetic';
    }
  }

  /* edges from the focused node */
  if(S.edges && focus && focus.top && focus.top.length){
    const fi = idx.get(focus.id), mw=Math.max(...(focus.tw||[1]));
    focus.top.forEach((id,k)=>{
      const j=idx.get(id); if(j===undefined) return;
      const n2=C.nodes[j]; if(!visible(n2,j)) return;
      const c=(focus.tw&&focus.tw[k])||1;
      ctx.beginPath(); ctx.moveTo(PX(fi),PY(fi)); ctx.lineTo(PX(j),PY(j));
      ctx.lineWidth=.6+2.8*(c/mw);
      ctx.strokeStyle=colourOf(focus,fi,.15+.45*(c/mw));
      ctx.stroke();
    });
  }

  /* nodes — Estonian ones last so thirteen pink dots stay findable among 2,379 */
  const order0=[...C.nodes.keys()].sort((a,b)=>{
    const ea2=(C.nodes[a].origin==='etkad'||C.nodes[a].etkad>0)?1:0;
    const eb2=(C.nodes[b].origin==='etkad'||C.nodes[b].etkad>0)?1:0;
    return ea2-eb2;
  });
  for(const i of order0){
    const n=C.nodes[i]; if(!visible(n,i)) continue;
    const X=PX(i), Y=PY(i); if(X<-40||X>w+40||Y<-40||Y>h+40) continue;
    let r=rad(n);
    if(!isMethod() && n.origin==='etkad') r=Math.max(r*2.1, 7);
    const on = (S.sel&&S.sel.id===n.id)||(S.hover&&S.hover.id===n.id);
    const inEE = ea && isMethod() && ea.has(n.id);
    const linked = focus && focus.top && focus.top.includes(n.id);
    ctx.beginPath(); ctx.arc(X,Y,on?r*1.55:r,0,6.284);
    ctx.fillStyle=colourOf(n,i, (ea&&isMethod()&&!inEE)?0.12:(on||linked?1:.75));
    ctx.fill();
    if(on||linked){ ctx.lineWidth=on?2:1.2;
      ctx.strokeStyle=on?'#fff':'rgba(255,255,255,.5)'; ctx.stroke(); }
    if(S.halo && ((isMethod()&&n.etkad>0)||(!isMethod()&&n.origin==='etkad'))){
      ctx.beginPath(); ctx.arc(X,Y,r+3.5,0,6.284);
      ctx.lineWidth=1.6; ctx.strokeStyle='rgba(255,92,138,.85)'; ctx.stroke();
    }
  }

  /* labels — one shared collision list, so cluster captions and node names
     never overprint each other. Bigger things claim their space first. */
  if(S.labels){
    const z=view.s/base.s;
    ctx.textAlign='center';
    const drawn=[];
    const fits=(box)=>!drawn.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1]);

    if(S.colour==='cluster'){
      for(const cl of [...C.clusters].sort((a,b)=>b.n-a.n)){
        const X=cl.x*view.s+view.tx, Y=cl.y*view.s+view.ty;
        if(X<0||X>w||Y<0||Y>h) continue;
        const fs=Math.max(10,Math.min(16,9+z*1.2));
        ctx.font='600 '+fs+'px sans-serif';
        const tw=ctx.measureText(cl.label).width;
        const box=[X-tw/2-4,Y-fs,X+tw/2+4,Y+4];
        if(!fits(box)) continue;
        drawn.push(box);
        ctx.lineWidth=3.5; ctx.strokeStyle='rgba(6,7,13,.9)';
        ctx.strokeText(cl.label,X,Y);
        ctx.fillStyle='rgba(255,255,255,.9)'; ctx.fillText(cl.label,X,Y);
      }
    }

    /* The 147 method names ARE the content of the method map, so they are
       always drawn, densest-first, rather than hidden behind a zoom gate. */
    const order=[...C.nodes.keys()].filter(i=>visible(C.nodes[i],i))
      .sort((a,b)=>nodeSize(C.nodes[b])-nodeSize(C.nodes[a]));
    const gate = true;   // ETKAD names show at any zoom; others gated inside
    if(gate){
      ctx.font='11px sans-serif';
      for(const i of order){
        const n=C.nodes[i];
        const isEE = !isMethod() && n.origin==='etkad';
        if(!isMethod() && !isEE && z<=3.2) continue;
        if(!isMethod() && !isEE && n.na<3 && z<5) continue;
        const X=PX(i),Y=PY(i); if(X<-20||X>w+20||Y<0||Y>h) continue;
        const on=(S.sel&&S.sel.id===n.id)||(S.hover&&S.hover.id===n.id);
        const t=nodeName(n).slice(0,34);
        const tw=ctx.measureText(t).width, ty=Y-rad(n)-4;
        const box=[X-tw/2-3,ty-11,X+tw/2+3,ty+3];
        if(!on && !isEE && !fits(box)) continue;   // focus + ETKAD always named
        drawn.push(box);
        ctx.lineWidth=3; ctx.strokeStyle='rgba(6,7,13,.88)';
        ctx.strokeText(t,X,ty);
        ctx.fillStyle= (ea&&isMethod()&&!ea.has(n.id))?'rgba(190,200,220,.32)'
                     : on?'#fff':'rgba(226,233,246,.9)';
        ctx.fillText(t,X,ty);
      }
    }
  }
  drawFoot(); drawLegend();
}
function drawFoot(){
  const C=cur(); let vis=0;
  for(let i=0;i<C.nodes.length;i++) if(visible(C.nodes[i],i)) vis++;
  document.getElementById('foot').textContent =
    `${vis} of ${C.nodes.length} ${isMethod()?'methods':'objects'} · `+
    `${C.clusters.length} clusters · metric: ${S.mode} · `+
    `${DATA.stats.sshomp} SSHOMP + ${DATA.stats.etkad} ETKAD`;
}
function drawLegend(){
  const el=document.getElementById('lgd'); let rows=[];
  if(S.colour==='group') rows=Object.entries(GROUP_COL);
  else if(S.colour==='cat') rows=Object.entries(CAT_COL).map(([k,v])=>[CAT_LAB[k]||k,v]);
  else if(S.colour==='ee') rows=[[isMethod()?'used by ETKAD':'ETKAD workflow','#ff5c8a'],
                                 [isMethod()?'not used':'SSHOMP object','#5a647c']];
  else if(S.colour==='gap') rows=[['only Europe uses it','#e0603a'],['both use it','#4ade80']];
  el.style.display = rows.length?'block':'none';
  el.innerHTML = rows.map(([k,v])=>`<div><i style="background:${v}"></i>${k}</div>`).join('');
}

/* ---------- picking + panel ---------- */
function pick(mx,my){
  const C=cur(); let best=null,bd=1e9;
  for(let i=0;i<C.nodes.length;i++){
    const n=C.nodes[i]; if(!visible(n,i)) continue;
    const dx=PX(i)-mx, dy=PY(i)-my, d=dx*dx+dy*dy, r=rad(n)+5;
    if(d<r*r&&d<bd){bd=d;best=n;}
  }
  return best;
}
const esc=s=>String(s==null?'':s).replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));

function show(n){
  S.sel=n;
  side.innerHTML = isMethod()? methodPanel(n) : itemPanel(n);
  side.querySelectorAll('[data-goto]').forEach(el=>el.onclick=()=>{
    const C=cur(); const t=C.nodes.find(x=>x.id===el.dataset.goto);
    if(t){ show(t); centre(t); }
  });
  side.querySelectorAll('[data-ee]').forEach(el=>el.onclick=()=>setEE(el.dataset.ee));
  side.querySelectorAll('[data-item]').forEach(el=>el.onclick=()=>{
    if(S.space!=='item') setSpace('item');
    const t=DATA.item.nodes.find(x=>x.id===el.dataset.item);
    if(t){ show(t); centre(t); }
  });
  draw();
}
function methodPanel(n){
  const ex=(n.ex||[]).map(e=>`<div class="row">${e.u?`<a href="${esc(e.u)}" target="_blank">${esc(e.n)}</a>`:esc(e.n)}<span>${esc(CAT_LAB[e.c]||e.c)}</span></div>`).join('');
  const co=(n.top||[]).map((t,i)=>`<span class="chip" data-goto="${esc(t)}">${esc(t)} <span style="color:#8590a8">${n.tw[i]}</span></span>`).join('');
  const users=DATA.item.nodes.filter(x=>x.origin==='etkad'&&x.acts.includes(n.id));
  return `<h2>${esc(n.id)}</h2>
   ${n.et?`<div style="color:#ff5c8a;font-size:13px;margin:-2px 0 4px">${esc(n.et)}</div>`:''}
   <div class="sub">TaDiRAH goal: <b>${esc(n.group)}</b> · used by <b>${n.n}</b> objects
     (${(100*n.n/DATA.stats.items).toFixed(1)}% of corpus)</div>
   <h4>Estonian uptake</h4>
   ${users.length?`<p>Used by <b>${users.length}</b> of ${DATA.stats.etkad} ETKAD workflows.</p>
     ${users.map(u=>`<div class="row"><a href="#" data-ee="${esc(u.id)}">${esc(u.label)}</a><span>click to overlay its method path</span></div>`).join('')}`
    :`<p class="empty">Not used by any ETKAD workflow. ${n.n} European objects use it — a candidate gap.</p>`}
   <h4>Most often combined with</h4><div>${co||'<span class="empty">nothing recurrent</span>'}</div>
   <h4>Example objects (${(n.ex||[]).length})</h4>${ex}`;
}
function itemPanel(n){
  const acts=(n.acts||[]).map(a=>`<span class="chip" data-goto="${esc(a)}">${esc(a)}</span>`).join('');
  if(n.origin==='etkad'){
    /* accordion titles already start with "1." on the ETKAD pages */
    const st=(n.stages||[]).map((s,i)=>`<div class="stage"><b>${/^\s*\d+\./.test(s.title)?'':(i+1)+'. '}${esc(s.title)}</b><br>
      ${s.acts.map(a=>`<span class="chip ee" data-goto="${esc(a)}">${esc(a)}</span>`).join('')}</div>`).join('');
    const rc=(n.recs||[]).map(r=>`<div class="row"><a href="${esc(r.u)}" target="_blank">${esc(r.n)}</a>
      <span>${esc(CAT_LAB[r.c]||r.c)} · similarity ${r.s} · shares ${esc(r.shared.join(', '))}</span></div>`).join('');
    return `<h2>${esc(n.label)}</h2>
     <div class="sub">ETKAD workflow · ${esc((n.disc||[]).join(', '))}
       ${n.lic?' · '+esc(n.lic):''}</div>
     ${n.authors&&n.authors.length?`<div class="sub">${esc(n.authors.join('; '))}</div>`:''}
     <p><a href="${esc(n.url)}" target="_blank">Open on etkad.ee ↗</a></p>
     <button class="btn act" data-ee="${esc(n.id)}">Show its path in method space</button>
     <h4>Method path (${(n.stages||[]).length} stages)</h4>${st||'<span class="empty">no stage breakdown on the page</span>'}
     <h4>Estonian TaDiRAH terms</h4><div>${(n.et||[]).map(t=>`<span class="chip">${esc(t)}</span>`).join('')}</div>
     <h4>Tools named in the text</h4>
     <p class="sub">Marketplace tools whose name literally appears on the workflow page —
       a direct statement of use, not an inferred similarity.</p>
     ${(n.named&&n.named.length)?n.named.map(t=>`<span class="chip" data-item="${esc(t.id)}">${esc(t.name)}</span>`).join(''):'<span class="empty">none matched</span>'}
     <h4>Closest European objects</h4>
     <p class="sub">By overlap of TaDiRAH methods — what others doing the same things have built.</p>
     ${rc||'<span class="empty">none</span>'}
     <h4>Output / media</h4><div class="sub">${esc((n.out||[]).join(', '))} · ${esc((n.media||[]).join(', '))}</div>`;
  }
  return `<h2>${esc(n.label)}</h2>
   <div class="sub">${esc(CAT_LAB[n.cat]||n.cat)}${n.src?' · '+esc(n.src):''}
     ${n.langs&&n.langs.length?' · '+esc(n.langs.join(', ')):''}</div>
   ${n.desc?`<p>${esc(n.desc)}</p>`:'<p class="empty">No description.</p>'}
   ${n.url?`<p><a href="${esc(n.url)}" target="_blank">Open ↗</a></p>`:''}
   <h4>Methods (${(n.acts||[]).length})</h4><div>${acts}</div>
   ${n.kw&&n.kw.length?`<h4>Keywords</h4><div>${n.kw.map(k=>`<span class="chip">${esc(k)}</span>`).join('')}</div>`:''}`;
}
function centre(n){
  const C=cur(), i=C.nodes.indexOf(n); if(i<0) return;
  view.tx=cv.clientWidth/2-C.xy[i][0]*view.s;
  view.ty=cv.clientHeight/2-C.xy[i][1]*view.s; draw();
}

/* ---------- gap report ---------- */
function gapReport(){
  S.sel=null;
  const rows=DATA.method.nodes.filter(n=>n.etkad===0).sort((a,b)=>b.n-a.n).slice(0,40);
  const used=DATA.method.nodes.filter(n=>n.etkad>0).sort((a,b)=>b.etkad-a.etkad).slice(0,15);
  side.innerHTML=`<h2>Method gap report</h2>
    <div class="sub">ETKAD workflows use <b>${DATA.stats.etkad_activities}</b> of
      <b>${DATA.stats.activities}</b> TaDiRAH methods present in the Marketplace.</div>
    <div class="bar"><span style="width:${100*DATA.stats.etkad_activities/DATA.stats.activities}%;background:#ff5c8a"></span><span style="flex:1;background:#243049"></span></div>
    <h4>Most used in Europe, unused in Estonia</h4>
    <table class="gap">${rows.map(r=>`<tr><td><a href="#" data-goto="${esc(r.id)}">${esc(r.id)}</a></td>
      <td style="color:#8590a8">${esc(r.group)}</td><td class="n">${r.n}</td></tr>`).join('')}</table>
    <h4>Most used by ETKAD</h4>
    <table class="gap">${used.map(r=>`<tr><td><a href="#" data-goto="${esc(r.id)}">${esc(r.id)}</a></td>
      <td class="n">${r.etkad}/${DATA.stats.etkad}</td><td class="n">${r.n}</td></tr>`).join('')}</table>
    <p class="sub" style="margin-top:14px">Right-hand number is how many European
      objects use the method; it is a rough measure of how well supported that
      method is by existing tools and training.</p>
    <p class="sub"><b>Read this as a tagging gap, not a practice gap.</b> A method
      counts as "unused" only when no ETKAD page carries its TaDiRAH term. Several
      entries below are plainly done in Estonia but left untagged — the photo-archive
      workflow surely involves <i>Imaging</i>, and transcription happens all over the
      corpus. That is exactly the point: discovery runs on what was declared, not on
      what was done.</p>`;
  side.querySelectorAll('[data-goto]').forEach(el=>el.onclick=(e)=>{
    e.preventDefault();
    if(S.space!=='method'){ setSpace('method'); }
    const t=DATA.method.nodes.find(x=>x.id===el.dataset.goto);
    if(t){ show(t); centre(t); }
  });
}

/* ---------- adjacent opportunities ----------
   Methods Estonia does not use, ranked not by raw popularity but by how tightly
   European practice binds them to methods Estonia ALREADY uses. "You do content
   analysis and NER; everyone who does those also does X" is a far more useful
   prompt than "X is popular". */
function adjReport(){
  S.sel=null;
  const rows=DATA.method.nodes.filter(n=>n.etkad===0 && n.n>=8 && n.adj>0)
    .sort((a,b)=>b.adj-a.adj).slice(0,28);
  side.innerHTML=`<h2>Adjacent opportunities</h2>
    <div class="sub">Methods no ETKAD workflow uses, ranked by how often European
      objects pair them with methods ETKAD <i>does</i> use. High score = a natural
      next step, not an unrelated speciality.</div>
    <table class="gap"><tr><td><b>method</b></td><td><b>goal</b></td>
      <td class="n"><b>tie</b></td><td class="n"><b>objects</b></td></tr>
      ${rows.map(r=>`<tr><td><a href="#" data-goto="${esc(r.id)}">${esc(r.id)}</a></td>
        <td style="color:#8590a8">${esc(r.group)}</td>
        <td class="n" style="color:#6fd3e8">${r.adj.toFixed(2)}</td>
        <td class="n">${r.n}</td></tr>`).join('')}</table>
    <p class="sub" style="margin-top:14px"><b>tie</b> is the mean number of
      already-used methods each European object combines with this one, divided by
      how many objects use it. Only methods with at least 8 European objects are
      listed, so the ranking is not driven by one-off tags.</p>`;
  side.querySelectorAll('[data-goto]').forEach(el=>el.onclick=(e)=>{
    e.preventDefault();
    if(S.space!=='method') setSpace('method');
    const t=DATA.method.nodes.find(x=>x.id===el.dataset.goto);
    if(t){ show(t); centre(t); }
  });
}

/* ---------- shape of a workflow (experimental) ----------
   Only the ETKAD side tags methods per stage IN ORDER, so this is the one
   question the Estonian data can answer and the Marketplace cannot: where in a
   workflow does each kind of method happen? Positions are normalised 0..1 so a
   4-stage and an 11-stage workflow are comparable. */
function shapeReport(){
  S.sel=null;
  const SH=DATA.shape;
  const bar=(d)=>{
    const c=GROUP_COL[d.g]||GROUP_COL.Other;
    return `<div style="font-size:12px;margin-top:9px">
       <span style="color:${c}">●</span> <b>${esc(d.g)}</b>
       <span style="color:#8590a8">· ${d.n} taggings</span></div>
      <div class="tl">
        <i style="left:${d.lo*100}%;width:${Math.max(1,(d.hi-d.lo)*100)}%;background:${c}"></i>
        <b style="left:calc(${d.mean*100}% - 1px);background:${c}"></b>
      </div>`;
  };
  const tr=SH.transitions.slice(0,12).map(t=>
    `<tr><td>${esc(t.from)}</td><td style="color:#8590a8">→</td><td>${esc(t.to)}</td>
      <td class="n">${t.n}</td></tr>`).join('');
  const late=SH.methods.filter(m=>m.mean>=0.66).slice(-10).reverse();
  const early=SH.methods.filter(m=>m.mean<=0.34).slice(0,10);
  side.innerHTML=`<h2>Shape of a workflow</h2>
    <div class="sub">Across ${SH.n_workflows} ETKAD workflows that break themselves into
      ordered stages. Bar = range of positions the goal appears at; tick = mean.
      0 is the first stage, 1 the last.</div>
    ${SH.groups.map(bar).join('')}
    <div class="tlx"><span>start</span><span>end</span></div>
    <h4>Most common goal transitions</h4>
    <table class="gap">${tr}</table>
    <h4>Earliest methods</h4>
    <div>${early.map(m=>`<span class="chip" data-goto="${esc(m.id)}">${esc(m.id)}</span>`).join('')}</div>
    <h4>Latest methods</h4>
    <div>${late.map(m=>`<span class="chip" data-goto="${esc(m.id)}">${esc(m.id)}</span>`).join('')}</div>
    <p class="sub" style="margin-top:14px">Only methods tagged in at least two stages
      anywhere in the corpus are listed, and the whole view rests on thirteen workflows —
      read it as a hypothesis about how humanities workflows are shaped, not a measurement.</p>`;
  side.querySelectorAll('[data-goto]').forEach(el=>el.onclick=(e)=>{
    e.preventDefault();
    if(S.space!=='method') setSpace('method');
    const t=DATA.method.nodes.find(x=>x.id===el.dataset.goto);
    if(t){ show(t); centre(t); }
  });
}

function downloadCSV(){
  const rows=[['method','tadirah_goal','estonian','european_objects',
               'etkad_workflows','adjacency_tie']];
  DATA.method.nodes.slice().sort((a,b)=>b.n-a.n).forEach(n=>
    rows.push([n.id,n.group,n.et||'',n.n,n.etkad,n.adj||0]));
  /* Build the line separator with fromCharCode rather than an escape.
     This template is a raw Python string and the two-character escape
     has been mangled into a real newline in the generated page before
     now, which silently breaks the entire script. */
  const NL=String.fromCharCode(10);
  const csv=rows.map(r=>r.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join(NL);
  const a=document.createElement('a');
  a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);
  a.download='tadirah-gap-analysis.csv'; a.click();
}

/* ---------- shareable state ---------- */
function encodeState(){
  const p=new URLSearchParams();
  p.set('sp',S.space); p.set('m',S.mode); p.set('c',S.colour);
  if(S.ee) p.set('ee',S.ee);
  if(S.sel) p.set('n',S.sel.id);
  if(S.q) p.set('q',S.q);
  return '#'+p.toString();
}
function applyState(){
  if(!location.hash) return;
  const p=new URLSearchParams(location.hash.slice(1));
  if(p.get('sp')&&p.get('sp')!==S.space) setSpace(p.get('sp'));
  if(p.get('m')&&DATA.modes.includes(p.get('m'))){ S.mode=p.get('m'); buildModeSeg(); }
  if(p.get('c')){ S.colour=p.get('c'); buildColour(); }
  if(p.get('q')){ S.q=p.get('q'); document.getElementById('q').value=S.q; }
  if(p.get('ee')) S.ee=p.get('ee');
  fit(false);
  if(p.get('n')){ const t=cur().nodes.find(x=>x.id===p.get('n')); if(t){show(t);centre(t);} }
}

/* ---------- controls ---------- */
function setSpace(v){
  S.space=v; S.mode=DATA.default_mode[v]; S.sel=null; S.hover=null;
  if(v==='method'&&!['cluster','group','ee','gap'].includes(S.colour)) S.colour='cluster';
  if(v==='item'&&!['cluster','cat','ee'].includes(S.colour)) S.colour='cluster';
  document.querySelectorAll('#spaceSeg button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  buildModeSeg(); buildColour(); buildFilters(); buildMinN();
  side.innerHTML=''; fit(false);
}
function buildModeSeg(){
  const el=document.getElementById('modeSeg');
  el.innerHTML=DATA.modes.map(m=>`<button data-v="${m}" class="${m===S.mode?'on':''}">${m}</button>`).join('');
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    S.mode=b.dataset.v;
    el.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));
    fit(false);
  });
}
function buildColour(){
  const sel=document.getElementById('colour');
  sel.innerHTML=COLOUR_OPTS[S.space].map(([v,l])=>`<option value="${v}">${l}</option>`).join('');
  sel.value=S.colour;
  sel.onchange=()=>{S.colour=sel.value; draw();};
}
function buildFilters(){
  const el=document.getElementById('filters');
  if(isMethod()){
    /* Filter the method map by TaDiRAH's own top-level goals. Useful for asking
       "show me only the Analysis methods and how they group among themselves". */
    const gs=[...new Set(DATA.method.nodes.map(n=>n.group))].sort();
    el.innerHTML=gs.map(g=>{
      const n=DATA.method.nodes.filter(x=>x.group===g).length;
      const on=!S.groups||S.groups.has(g);
      return `<label class="ck"><input type="checkbox" data-g="${g}" ${on?'checked':''}>
        <span style="color:${GROUP_COL[g]||'#8b95ab'}">●</span> ${g}
        <span style="color:#8590a8">${n}</span></label>`;}).join('');
    el.querySelectorAll('input').forEach(i=>i.onchange=()=>{
      const all=[...new Set(DATA.method.nodes.map(n=>n.group))];
      if(!S.groups) S.groups=new Set(all);
      i.checked?S.groups.add(i.dataset.g):S.groups.delete(i.dataset.g);
      if(S.groups.size===all.length) S.groups=null;
      draw();
    });
    return;
  }
  el.innerHTML=Object.entries(DATA.stats.cats).sort((a,b)=>b[1]-a[1]).map(([c,n])=>
    `<label class="ck"><input type="checkbox" data-c="${c}" ${S.cats.has(c)?'checked':''}>
      <span style="color:${CAT_COL[c]||'#8b95ab'}">●</span> ${CAT_LAB[c]||c} <span style="color:#8590a8">${n}</span></label>`).join('');
  el.innerHTML+=`<input type="text" id="srcq" placeholder="source contains…"
     style="margin-top:7px" value="${S.srcq}">
    <input type="text" id="langq" placeholder="language contains…"
     style="margin-top:5px" value="${S.langq}">`;
  el.querySelectorAll('input[data-c]').forEach(i=>i.onchange=()=>{
    i.checked?S.cats.add(i.dataset.c):S.cats.delete(i.dataset.c); draw();
  });
  el.querySelector('#srcq').oninput=e=>{S.srcq=e.target.value.trim().toLowerCase();draw();};
  el.querySelector('#langq').oninput=e=>{S.langq=e.target.value.trim().toLowerCase();draw();};
}
function buildMinN(){
  const r=document.getElementById('minN');
  r.max = isMethod()? 60 : 12; r.value=1; S.minN=1; updMinN();
  r.oninput=()=>{S.minN=+r.value; updMinN(); draw();};
}
function updMinN(){
  document.getElementById('minNlab').textContent =
    isMethod()? `methods used by ≥ ${S.minN} objects` : `objects with ≥ ${S.minN} methods`;
}
function buildEE(){
  const el=document.getElementById('eeList');
  const ws=DATA.item.nodes.filter(n=>n.origin==='etkad');
  el.innerHTML=ws.map(w=>`<div class="row" style="cursor:pointer" data-ee="${w.id}">
     ${esc(w.label.slice(0,52))}<span>${w.acts.length} methods · ${(w.stages||[]).length} stages</span></div>`).join('');
  el.querySelectorAll('[data-ee]').forEach(d=>d.onclick=()=>setEE(d.dataset.ee));
}
function setEE(id){
  S.ee = (S.ee===id)? null : id;
  if(S.ee){
    const w=DATA.item.nodes.find(n=>n.id===S.ee);
    if(S.space!=='method'){ setSpace('method'); }
    if(w){ side.innerHTML=itemPanel(w);
      side.querySelectorAll('[data-goto]').forEach(el=>el.onclick=()=>{
        const t=DATA.method.nodes.find(x=>x.id===el.dataset.goto);
        if(t){ show(t); centre(t);} });
      side.querySelectorAll('[data-ee]').forEach(el=>el.onclick=()=>setEE(el.dataset.ee));
    }
  }
  draw();
}

/* ---------- interaction ---------- */
let drag=null;
cv.addEventListener('mousedown',e=>{drag={x:e.offsetX,y:e.offsetY,tx:view.tx,ty:view.ty,m:0};cv.classList.add('drag');});
window.addEventListener('mouseup',()=>{cv.classList.remove('drag');drag=null;});
cv.addEventListener('mousemove',e=>{
  if(drag){ drag.m+=Math.abs(e.movementX)+Math.abs(e.movementY);
    view.tx=drag.tx+e.offsetX-drag.x; view.ty=drag.ty+e.offsetY-drag.y;
    tip.style.display='none'; draw(); return; }
  const n=pick(e.offsetX,e.offsetY);
  if(n!==S.hover){ S.hover=n; draw(); }
  if(n){ tip.style.display='block';
    tip.innerHTML = isMethod()
      ? `<b>${esc(n.id)}</b> — ${n.n} objects${n.etkad?` · <span style="color:#ff5c8a">${n.etkad} ETKAD</span>`:''}<br><span style="color:#8590a8">${esc(n.group)}${n.et?' · '+esc(n.et):''}</span>`
      : `<b>${esc(n.label.slice(0,70))}</b><br><span style="color:#8590a8">${esc(CAT_LAB[n.cat]||n.cat)} · ${n.na} methods</span>`;
    const bx=Math.min(e.offsetX+14, cv.clientWidth-350);
    tip.style.left=bx+'px'; tip.style.top=(e.offsetY+14)+'px';
  } else tip.style.display='none';
});
cv.addEventListener('click',e=>{ if(drag&&drag.m>4) return;
  const n=pick(e.offsetX,e.offsetY); if(n) show(n); });
cv.addEventListener('wheel',e=>{ e.preventDefault();
  const k=Math.exp(-e.deltaY*0.0016);
  const ns=Math.max(base.s*.3,Math.min(base.s*90,view.s*k)), r=ns/view.s;
  view.tx=e.offsetX-(e.offsetX-view.tx)*r; view.ty=e.offsetY-(e.offsetY-view.ty)*r;
  view.s=ns; draw();
},{passive:false});

document.querySelectorAll('#spaceSeg button').forEach(b=>b.onclick=()=>setSpace(b.dataset.v));
document.getElementById('q').addEventListener('input',e=>{S.q=e.target.value.trim().toLowerCase();draw();});
document.getElementById('reset').onclick=()=>{view={...base};draw();};
document.getElementById('clearEE').onclick=()=>{S.ee=null;draw();};
document.getElementById('gapBtn').onclick=gapReport;
document.getElementById('adjBtn').onclick=adjReport;
document.getElementById('shapeBtn').onclick=shapeReport;
document.getElementById('csvBtn').onclick=downloadCSV;
document.getElementById('lab').onchange=e=>{S.labels=e.target.checked;draw();};
document.getElementById('edg').onchange=e=>{S.edges=e.target.checked;draw();};
document.getElementById('halo').onchange=e=>{S.halo=e.target.checked;draw();};
document.getElementById('dens').onchange=e=>{S.dens=e.target.checked;draw();};
document.getElementById('png').onclick=()=>{
  const a=document.createElement('a');
  a.download='method-galaxy-'+S.space+'-'+S.mode+'.png';
  a.href=cv.toDataURL('image/png'); a.click();
};
document.getElementById('link').onclick=(e)=>{
  const url=location.href.split('#')[0]+encodeState();
  history.replaceState(null,'',encodeState());
  navigator.clipboard?.writeText(url);
  e.target.textContent='Link copied ✓';
  setTimeout(()=>e.target.textContent='Copy link to this view',1600);
};
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT') return;
  if(e.key==='m') setSpace(S.space==='method'?'item':'method');
  if(e.key==='r'){ view={...base}; draw(); }
  if(e.key==='l'){ S.labels=!S.labels; document.getElementById('lab').checked=S.labels; draw(); }
  if(e.key==='Escape'){ S.sel=null; S.ee=null; draw(); }
});
window.addEventListener('resize',()=>fit(true));

buildModeSeg(); buildColour(); buildFilters(); buildMinN(); buildEE();
side.innerHTML=`<h2>DH Method Galaxy</h2>
  <div class="sub">${DATA.stats.sshomp} objects from the SSH Open Marketplace and
    ${DATA.stats.etkad} ETKAD workflows, placed by the TaDiRAH methods they share.</div>
  <p><b>Methods</b> space: ${DATA.stats.activities} TaDiRAH activities, near each other
   when the same objects use them.</p>
  <p><b>Objects</b> space: every tool, dataset, tutorial and workflow, near each other
   when they share methods.</p>
  <p>Pick an Estonian workflow in the left rail to draw its <b>method path</b> through the
   map, or open the <b>gap report</b> to see which methods Europe uses and Estonia does not.</p>
  <p class="sub">Estonian terms were joined to TaDiRAH2 by translation — TaDiRAH publishes
   English labels only.</p>
  <p class="sub">Keys: <b>m</b> switch space · <b>r</b> reset view · <b>l</b> labels ·
   <b>Esc</b> clear selection.</p>`;
fit(false);
applyState();
</script>
</body>
</html>
"""


def main():
    data = json.load(open(os.path.join(WORK, "layout.json"), encoding="utf-8"))
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"),
                                                   ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"-> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB, "
          f"{len(data['method']['nodes'])} methods, {len(data['item']['nodes'])} objects)")


if __name__ == "__main__":
    main()
