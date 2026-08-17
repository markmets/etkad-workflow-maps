#!/usr/bin/env python3
"""Stage 4: render layout.json into a single self-contained interactive HTML.

No CDN, no server, no build step — canvas 2D handles this node count fine and
keeps the output a single portable file.

Output: galaxy_map.html
"""
import json
import os

WORK = os.path.abspath(os.environ.get("WFGAL_WORK", "./work"))
OUT = os.path.abspath(os.environ.get("WFGAL_OUT", "./galaxy_map.html"))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Workflow Galaxy — tools by co-usage</title>
<style>
  :root { --bg:#07080f; --fg:#e8ecf5; --dim:#8892a8; --line:#1e2436; --accent:#6fd3e8; }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--fg);
    font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  #wrap { display:flex; height:100%; }
  #stage { flex:1; position:relative; }
  canvas { display:block; width:100%; height:100%; cursor:grab; }
  canvas.drag { cursor:grabbing; }
  #hud { position:absolute; top:14px; left:14px; display:flex; gap:8px;
    align-items:center; flex-wrap:wrap; z-index:5; }
  input,button { background:rgba(18,22,34,.92); color:var(--fg);
    border:1px solid var(--line); border-radius:7px; padding:7px 11px; font:inherit; }
  input { width:230px; }
  input:focus { outline:none; border-color:var(--accent); }
  button { cursor:pointer; }
  button:hover { border-color:var(--accent); }
  #tip { position:absolute; pointer-events:none; background:rgba(10,13,22,.96);
    border:1px solid var(--line); border-radius:7px; padding:6px 10px; font-size:12px;
    display:none; z-index:9; white-space:nowrap; }
  #side { width:355px; border-left:1px solid var(--line); background:#0b0e18;
    overflow-y:auto; padding:20px; }
  #side h2 { margin:0 0 2px; font-size:19px; }
  #side .sub { color:var(--dim); font-size:12px; margin-bottom:14px; }
  #side h3 { font-size:11px; text-transform:uppercase; letter-spacing:.09em;
    color:var(--dim); margin:20px 0 7px; font-weight:600; }
  #side p { margin:0 0 10px; color:#c3cbdd; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .chip { display:inline-block; background:#151b2b; border:1px solid var(--line);
    border-radius:20px; padding:3px 11px; margin:0 5px 5px 0; cursor:pointer;
    font-size:12px; }
  .chip:hover { border-color:var(--accent); color:var(--accent); }
  .wf { padding:5px 0; border-bottom:1px solid #141a29; font-size:12px; }
  .wf span { color:var(--dim); font-size:10.5px; display:block; }
  .empty { color:var(--dim); font-style:italic; }
  #foot { position:absolute; bottom:12px; left:14px; color:var(--dim); font-size:11px; }
  .lgd { position:absolute; bottom:12px; right:14px; color:var(--dim); font-size:11px;
    text-align:right; }
  #srclgd { position:absolute; bottom:34px; right:14px; font-size:11px; text-align:right;
    display:none; }
  #srclgd div { margin:2px 0; }
  #srclgd i { display:inline-block; width:9px; height:9px; border-radius:50%;
    margin-right:6px; }
  label.chk { display:inline-flex; align-items:center; gap:6px; cursor:pointer;
    background:rgba(18,22,34,.92); border:1px solid var(--line); border-radius:7px;
    padding:7px 11px; }
  label.chk:hover { border-color:var(--accent); }
  .bar { height:5px; border-radius:3px; background:#151b2b; margin:3px 0 8px;
    overflow:hidden; display:flex; }
</style>
</head>
<body>
<div id="wrap">
  <div id="stage">
    <canvas id="cv"></canvas>
    <div id="hud">
      <input id="q" placeholder="Search tools…" autocomplete="off">
      <button id="reset">Reset view</button>
      <button id="toggle">Labels: on</button>
      <button id="cmode">Colour: cluster</button>
      <label class="chk"><input type="checkbox" id="doionly"> DOI only</label>
      <label class="chk"><input type="checkbox" id="edges" checked> Edges</label>
    </div>
    <div id="tip"></div>
    <div id="foot"></div>
    <div id="srclgd"></div>
    <div class="lgd">scroll to zoom · drag to pan · click a dot</div>
  </div>
  <div id="side">
    <h2>Workflow Galaxy</h2>
    <div class="sub">Each dot is a software tool. Tools sit near each other when
      they are used together in the same workflows.</div>
    <p class="empty">Click any dot for details.</p>
  </div>
</div>
<script>
const DATA = __DATA__;
const nodes = DATA.nodes, clusters = DATA.clusters;
const byId = new Map(nodes.map(n => [n.id, n]));
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const tip = document.getElementById('tip'), side = document.getElementById('side');

// Frame the bulk, not the extremes. UMAP flings a handful of near-singleton
// tools far outside the main mass; fitting to min/max let ~10 of them squash
// all 750 others into an illegible smudge in the middle.
function pct(arr, p) {
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.round(p * (s.length - 1))))];
}
const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
const bounds = { x0: pct(xs, 0.04), x1: pct(xs, 0.96),
                 y0: pct(ys, 0.04), y1: pct(ys, 0.96) };
const maxN = Math.max(...nodes.map(n => n.n));
let view = { s: 1, tx: 0, ty: 0 }, base = null;
let hover = null, sel = null, showLabels = true, matches = null;
let colourMode = 'cluster', doiOnly = false, showEdges = true;

// Source families. nf-core / Galaxy / WorkflowHub / Dockstore are all life
// sciences; `dh` is the humanities corner, and its position and sparseness
// relative to everything else is the point of colouring by source at all.
const SRC = {
  'nf-core':    ['#4ade80', 'nf-core'],
  'galaxy':     ['#60a5fa', 'Galaxy (IWC + training)'],
  'workflowhub':['#c084fc', 'WorkflowHub'],
  'dockstore':  ['#fb923c', 'Dockstore'],
  'dh':         ['#f472b6', 'DH notebooks'],
  'other':      ['#94a3b8', 'other'],
};
function colour(c, a) {
  if (c < 0) return `rgba(105,115,140,${a})`;
  const h = (c * 47) % 360;
  return `hsla(${h},68%,63%,${a})`;
}
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
}
function nodeColour(n, a) {
  if (colourMode === 'source') return hexA((SRC[n.src] || SRC.other)[0], a);
  return colour(n.c, a);
}
const visible = n => !doiOnly || !!n.doi;
function fit() {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  cv.width = w * dpr; cv.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const pad = 60;
  const sx = (w - pad * 2) / (bounds.x1 - bounds.x0 || 1);
  const sy = (h - pad * 2) / (bounds.y1 - bounds.y0 || 1);
  const s = Math.min(sx, sy);
  base = { s, tx: pad - bounds.x0 * s + (w - pad * 2 - (bounds.x1 - bounds.x0) * s) / 2,
           ty: pad - bounds.y0 * s + (h - pad * 2 - (bounds.y1 - bounds.y0) * s) / 2 };
  if (!fit.done) { view = { ...base }; fit.done = true; }
  draw();
}
const px = n => n.x * view.s + view.tx;
const py = n => n.y * view.s + view.ty;
const rad = n => Math.max(2.2, Math.sqrt(n.n / maxN) * 17) * Math.min(1.9, Math.max(.55, view.s / base.s));

function draw() {
  const w = cv.clientWidth, h = cv.clientHeight;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#07080f'; ctx.fillRect(0, 0, w, h);

  // Edges from the focused tool to its strongest co-occurrences. Drawn only on
  // focus: the full co-occurrence graph is far too dense to read at once, and
  // the interesting question is always "what goes with THIS tool".
  const focus = hover || sel;
  if (showEdges && focus && focus.top && focus.top.length) {
    const maxW = Math.max(...(focus.tw || [1]));
    focus.top.forEach((id, i) => {
      const m = byId.get(id);
      if (!m || !visible(m)) return;
      const c = (focus.tw && focus.tw[i]) || 1;
      ctx.beginPath();
      ctx.moveTo(px(focus), py(focus)); ctx.lineTo(px(m), py(m));
      ctx.lineWidth = 0.6 + 2.6 * (c / maxW);
      ctx.strokeStyle = nodeColour(focus, 0.16 + 0.42 * (c / maxW));
      ctx.stroke();
    });
  }

  for (const n of nodes) {
    if (!visible(n)) continue;
    const X = px(n), Y = py(n), r = rad(n);
    if (X < -30 || X > w + 30 || Y < -30 || Y > h + 30) continue;
    const dim = matches && !matches.has(n.id);
    const on = sel === n || hover === n;
    const linked = focus && focus !== n && showEdges && focus.top &&
                   focus.top.includes(n.id);
    ctx.beginPath(); ctx.arc(X, Y, on ? r * 1.5 : r, 0, 6.284);
    ctx.fillStyle = nodeColour(n, dim ? 0.07 : (on || linked ? 1 : 0.72));
    ctx.fill();
    if (on || linked) {
      ctx.lineWidth = on ? 2 : 1.2;
      ctx.strokeStyle = on ? '#fff' : 'rgba(255,255,255,.55)';
      ctx.stroke();
    }
  }
  if (showLabels) {
    const zoomed = view.s / base.s;
    ctx.textAlign = 'center';
    if (colourMode === 'cluster' && !doiOnly) {
      // Biggest clusters get their label first; anything that would overlap an
      // already-drawn one is dropped. Overlapping labels were unreadable.
      const drawn = [];
      const ordered = [...clusters].sort((a, b) => b.n - a.n);
      for (const c of ordered) {
        const X = c.x * view.s + view.tx, Y = c.y * view.s + view.ty;
        if (X < 0 || X > w || Y < 0 || Y > h) continue;
        const fs = Math.max(10, Math.min(16, 9 + zoomed * 1.2));
        ctx.font = '600 ' + fs + 'px sans-serif';
        const tw = ctx.measureText(c.label).width;
        const box = [X - tw / 2 - 4, Y - fs, X + tw / 2 + 4, Y + 4];
        if (drawn.some(b => box[0] < b[2] && box[2] > b[0] &&
                            box[1] < b[3] && box[3] > b[1])) continue;
        drawn.push(box);
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(7,8,15,.85)';
        ctx.strokeText(c.label, X, Y);
        ctx.fillStyle = 'rgba(255,255,255,.88)';
        ctx.fillText(c.label, X, Y);
      }
    }
    if (zoomed > 2.4 || doiOnly) {
      ctx.font = '11px sans-serif';
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(7,8,15,.8)';
      for (const n of nodes) {
        if (!visible(n)) continue;
        if (n.n < 3 && zoomed < 4 && !doiOnly) continue;
        if (matches && !matches.has(n.id)) continue;
        ctx.strokeText(n.id, px(n), py(n) - rad(n) - 4);
        ctx.fillStyle = 'rgba(220,228,244,.85)';
        ctx.fillText(n.id, px(n), py(n) - rad(n) - 4);
      }
    }
    // Always name the neighbours of the focused tool, at any zoom.
    if (showEdges && focus && focus.top) {
      ctx.font = '11px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,.9)';
      for (const id of focus.top) {
        const m = byId.get(id);
        if (m && visible(m)) ctx.fillText(m.id, px(m), py(m) - rad(m) - 4);
      }
    }
  }
  const shown = doiOnly ? nodes.filter(visible).length : DATA.stats.tools;
  document.getElementById('foot').textContent =
    `${shown}${doiOnly ? ' of ' + DATA.stats.tools : ''} tools · ` +
    `${DATA.stats.workflows} workflows · ${clusters.length} clusters · ` +
    `sources: ${DATA.stats.sources.join(', ')}`;
}

function pick(mx, my) {
  let best = null, bd = 1e9;
  for (const n of nodes) {
    if (!visible(n)) continue;
    const dx = px(n) - mx, dy = py(n) - my, d = dx * dx + dy * dy;
    const r = rad(n) + 4;
    if (d < r * r && d < bd) { bd = d; best = n; }
  }
  return best;
}
function esc(s) { return String(s || '').replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c])); }

function show(n) {
  sel = n;
  const doi = n.doi ? `<a href="https://doi.org/${esc(n.doi)}" target="_blank">${esc(n.doi)}</a>` : '';
  const cl = clusters.find(c => c.c === n.c);
  const srcs = n.srcs || {};
  const tot = Object.values(srcs).reduce((a, b) => a + b, 0) || 1;
  const bar = Object.entries(srcs).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
    `<span style="width:${(100 * v / tot).toFixed(1)}%;background:${(SRC[k] || SRC.other)[0]}"
      title="${esc(k)}: ${v}"></span>`).join('');
  side.innerHTML = `
    <h2>${esc(n.label)}</h2>
    <div class="sub">${esc(n.id)} · used in <b>${n.n}</b> workflow${n.n > 1 ? 's' : ''}
      ${cl ? ' · <span style="color:' + colour(n.c, 1) + '">' + esc(cl.label) + '</span>' : ''}</div>
    <div class="bar">${bar}</div>
    <div class="sub">${Object.entries(srcs).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `${esc((SRC[k] || SRC.other)[1])} ${v}`).join(' · ')}</div>
    ${n.desc ? `<p>${esc(n.desc)}</p>` : '<p class="empty">No description available — this tool was named by a workflow step (a Galaxy tool_id, a container image, an import) that no metadata registry describes. Thin metadata is the normal case, not the exception.</p>'}
    ${n.url ? `<p><a href="${esc(n.url)}" target="_blank">Homepage ↗</a></p>` : ''}
    ${doi ? `<h3>Method paper</h3><p>${doi}</p>` : ''}
    ${n.lic ? `<div class="sub">Licence: ${esc(n.lic)}</div>` : ''}
    <h3>Most often used with</h3>
    <div>${n.top.length ? n.top.map((t, i) => `<span class="chip" data-t="${esc(t)}">${esc(t)}${n.tw ? ' <span style="color:#8892a8">' + n.tw[i] + '</span>' : ''}</span>`).join('') : '<span class="empty">nothing recurrent</span>'}</div>
    <h3>Workflows (${n.wfs.length}${n.n > n.wfs.length ? ' of ' + n.n : ''})</h3>
    ${n.wfs.map(w => `<div class="wf">${w.u ? `<a href="${esc(w.u)}" target="_blank">${esc(w.n)}</a>` : esc(w.n)}<span>${esc(w.s)}</span></div>`).join('')}
  `;
  side.querySelectorAll('.chip').forEach(el => el.onclick = () => {
    const t = byId.get(el.dataset.t);
    if (t) { show(t); centre(t); }
  });
  draw();
}
function centre(n) {
  view.tx = cv.clientWidth / 2 - n.x * view.s;
  view.ty = cv.clientHeight / 2 - n.y * view.s;
  draw();
}

let drag = null;
cv.addEventListener('mousedown', e => { drag = { x: e.offsetX, y: e.offsetY, tx: view.tx, ty: view.ty, moved: 0 }; cv.classList.add('drag'); });
window.addEventListener('mouseup', () => { cv.classList.remove('drag'); drag = null; });
cv.addEventListener('mousemove', e => {
  if (drag) {
    drag.moved += Math.abs(e.movementX) + Math.abs(e.movementY);
    view.tx = drag.tx + e.offsetX - drag.x; view.ty = drag.ty + e.offsetY - drag.y;
    tip.style.display = 'none'; draw(); return;
  }
  const n = pick(e.offsetX, e.offsetY);
  if (n !== hover) { hover = n; draw(); }
  if (n) {
    tip.style.display = 'block';
    tip.textContent = `${n.id} — ${n.n} workflow${n.n > 1 ? 's' : ''}`;
    tip.style.left = (e.offsetX + 14) + 'px'; tip.style.top = (e.offsetY + 14) + 'px';
  } else tip.style.display = 'none';
});
cv.addEventListener('click', e => {
  if (drag && drag.moved > 4) return;
  const n = pick(e.offsetX, e.offsetY);
  if (n) show(n);
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const k = Math.exp(-e.deltaY * 0.0016);
  const ns = Math.max(base.s * 0.35, Math.min(base.s * 70, view.s * k));
  const r = ns / view.s;
  view.tx = e.offsetX - (e.offsetX - view.tx) * r;
  view.ty = e.offsetY - (e.offsetY - view.ty) * r;
  view.s = ns; draw();
}, { passive: false });

document.getElementById('q').addEventListener('input', e => {
  const v = e.target.value.trim().toLowerCase();
  if (!v) { matches = null; draw(); return; }
  matches = new Set(nodes.filter(n =>
    n.id.includes(v) || (n.label || '').toLowerCase().includes(v) ||
    (n.desc || '').toLowerCase().includes(v)).map(n => n.id));
  draw();
});
document.getElementById('reset').onclick = () => { view = { ...base }; draw(); };
document.getElementById('toggle').onclick = e => {
  showLabels = !showLabels;
  e.target.textContent = 'Labels: ' + (showLabels ? 'on' : 'off'); draw();
};
const srclgd = document.getElementById('srclgd');
srclgd.innerHTML = Object.entries(SRC).map(([k, v]) =>
  `<div><i style="background:${v[0]}"></i>${v[1]}</div>`).join('');
document.getElementById('cmode').onclick = e => {
  colourMode = colourMode === 'cluster' ? 'source' : 'cluster';
  e.target.textContent = 'Colour: ' + colourMode;
  srclgd.style.display = colourMode === 'source' ? 'block' : 'none';
  draw();
};
document.getElementById('doionly').onchange = e => { doiOnly = e.target.checked; draw(); };
document.getElementById('edges').onchange = e => { showEdges = e.target.checked; draw(); };
window.addEventListener('resize', fit);
fit();
</script>
</body>
</html>
"""


def main() -> None:
    data = json.load(open(os.path.join(WORK, "layout.json"), encoding="utf-8"))
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    kb = os.path.getsize(OUT) / 1024
    print(f"-> {OUT}  ({kb:.0f} KB, {len(data['nodes'])} nodes, "
          f"{len(data['clusters'])} clusters)")


if __name__ == "__main__":
    main()
