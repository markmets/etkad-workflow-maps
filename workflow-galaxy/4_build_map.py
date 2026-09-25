#!/usr/bin/env python3
"""Stage 4: render the atlas as one self-contained HTML file.

The interaction that matters is the facet weights. Everything else on the page —
positions, neighbour lists, cluster labels, the transition graph — is downstream
of "which aspects of a workflow do you mean by similar". Similarity is therefore
recomputed in the browser from the shipped sparse vectors every time a slider
moves, rather than being baked in.

RENDERING NOTES (the second version fixed all of these)
  * Label placement is viewport-first. The earlier version ranked every node,
    took the top 70, and only then discarded the off-screen ones — so zooming in
    spent the whole label budget on nodes nobody could see and the visible ones
    went unlabelled.
  * Labels appear by degrees as you zoom rather than all at once past a hard
    threshold, and collision testing uses a real rectangle overlap (the old test
    mixed a centre-line y with a top-edge y and let labels sit on top of one
    another).
  * Node radius grows sub-linearly with zoom. At fixed radius a zoomed-in map is
    a few specks adrift in emptiness.
  * The detail panel no longer covers the thing you selected: the drawing
    viewport is inset by the panel width and the selection is eased into the
    remaining space.

Design follows the usual guidance for graph UIs: progressive disclosure over
showing everything, a colourblind-safe palette (Okabe-Ito), shape as well as
colour so the encoding survives greyscale, restrained accents, and one clear
z-order so no panel ever hides data without saying so.

No CDN, no external anything: the file opens from disk.

Output: workflow_galaxy.html
"""
import datetime
import json
import os
import sys

WORK = os.path.abspath(os.environ.get("WFA_WORK", "./work"))
OUT = os.path.abspath(os.environ.get("WFA_OUT", "./workflow_galaxy.html"))

TPL = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workflow Galaxy</title>
<style>
/* Two themes, because a reading audience should not have to accept ours. Dark is
   built on #15151a rather than pure black: full black against light text causes
   halation, the glow that makes small type swim. Light is a warm paper white for
   the same reason in reverse. Body weight is 400 on light and 350-ish optical on
   dark, where thin strokes bloom. */
:root{
  --bg:#15151a; --panel:#1b1b21; --panel2:#212129; --line:#2e2e37;
  --ink:#eceae6; --ink2:#adaba8; --ink3:#79777c; --ink4:#57555c;
  --accent:#e0a458; --accent2:#8fbfe0;
  --mp:#56b4e9; --ph:#e69f00; --etkad:#cc79a7;
  --shadow:0 10px 34px #00000070;
  --veil:rgba(21,21,26,.90); --scrim:rgba(21,21,26,.86);
  --tint:rgba(224,164,88,.13); --tintline:rgba(224,164,88,.45);
  --toolline:rgba(230,159,0,.42); --topicline:rgba(143,191,224,.38);
  --linkline:rgba(143,191,224,.40);
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --base:15px;
}
:root[data-theme="light"]{
  --bg:#faf8f4; --panel:#fffdfa; --panel2:#f2efe9; --line:#e0dcd3;
  --ink:#22201d; --ink2:#55524d; --ink3:#807c75; --ink4:#a8a49c;
  --accent:#a8620d; --accent2:#1f6d9e;
  --mp:#2f7fb5; --ph:#b06d00; --etkad:#a94c81;
  --shadow:0 8px 26px #2a231a1f;
  --veil:rgba(250,248,244,.92); --scrim:rgba(250,248,244,.88);
  --tint:rgba(168,98,13,.09); --tintline:rgba(168,98,13,.40);
  --toolline:rgba(176,109,0,.45); --topicline:rgba(31,109,158,.40);
  --linkline:rgba(31,109,158,.40);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
  font:var(--base)/1.55 var(--sans);overflow:hidden;
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
#app{display:flex;height:100%}

/* ---------- left rail ---------- */
#rail{width:330px;flex:0 0 330px;background:var(--panel);
  border-right:1px solid var(--line);overflow-y:auto;overscroll-behavior:contain}
#rail::-webkit-scrollbar,#detail::-webkit-scrollbar{width:10px}
#rail::-webkit-scrollbar-thumb,#detail::-webkit-scrollbar-thumb{
  background:var(--ink4);border-radius:10px;border:3px solid var(--panel)}
.masthead{padding:20px 22px 16px;border-bottom:1px solid var(--line)}
.masthead .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.masthead h1{font:400 24px/1.15 var(--serif);margin:0;letter-spacing:.1px;color:var(--ink)}
.masthead p{margin:8px 0 0;color:var(--ink2);font-size:13px;line-height:1.55}
.prefs{display:flex;gap:4px;flex:0 0 auto}
.prefs button{padding:4px 7px;font-size:12px;line-height:1}
section{padding:18px 22px;border-bottom:1px solid var(--line)}
section:last-child{border-bottom:0;padding-bottom:48px}
.sechead{display:flex;align-items:center;justify-content:space-between;
  margin:0 0 6px;cursor:pointer;user-select:none;gap:8px}
.sechead h2{font:600 11.5px/1.3 var(--sans);text-transform:uppercase;
  letter-spacing:1.2px;color:var(--ink2);margin:0}
.sechead .caret{color:var(--ink4);font-size:10px;transition:transform .15s;flex:0 0 auto}
section.closed .caret{transform:rotate(-90deg)}
section.closed .body{display:none}
.hint{color:var(--ink2);font-size:13px;line-height:1.6;margin:8px 0 14px}
.hint em{color:var(--ink3);font-style:italic}
.aside{color:var(--ink3);font-size:12.5px;line-height:1.55;margin:8px 0 0;
  padding-left:11px;border-left:2px solid var(--line)}

/* sliders */
.fac{margin:0 0 15px}
.fac .top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.fac .name{font-weight:600;font-size:14px;color:var(--ink);letter-spacing:.1px}
.fac .val{font-size:12px;color:var(--accent);min-width:34px;text-align:right;
  font-weight:600}
.fac .desc{color:var(--ink3);font-size:12.5px;margin:1px 0 5px;line-height:1.45}
.fac.off .name,.fac.off .val,.fac.off .desc{color:var(--ink4)}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:14px;
  background:transparent;cursor:pointer;margin:0;display:block}
input[type=range]::-webkit-slider-runnable-track{height:3px;border-radius:3px;
  background:#31313a}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:13px;height:13px;
  border-radius:50%;background:var(--accent);margin-top:-5px;
  border:2px solid var(--panel);box-shadow:0 0 0 1px #00000060}
/* Firefox needs its own pseudo-elements; without these the track and thumb fall
   back to the platform default and the control looks broken against the rail. */
input[type=range]::-moz-range-track{height:3px;border-radius:3px;background:#31313a;
  border:0}
input[type=range]::-moz-range-thumb{width:11px;height:11px;border-radius:50%;
  background:var(--accent);border:2px solid var(--panel)}
input[type=range]:focus-visible{outline:2px solid var(--accent2);outline-offset:3px}

/* controls */
.btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
button{background:var(--panel2);color:var(--ink2);border:1px solid var(--line);
  border-radius:6px;padding:6px 11px;font:500 13px var(--sans);cursor:pointer;
  transition:background .12s,color .12s,border-color .12s}
button:hover{background:var(--line);color:var(--ink)}
button:focus-visible{outline:2px solid var(--accent2);outline-offset:2px}
button.primary{border-color:var(--accent);color:var(--accent);background:transparent}
button.primary:hover{background:var(--panel2)}
button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
select,input[type=text]{width:100%;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);border-radius:6px;padding:8px 10px;
  font:13.5px var(--sans)}
select:focus,input[type=text]:focus{outline:2px solid var(--accent2);
  outline-offset:1px;border-color:transparent}
label.fieldlabel{display:block;font-size:12.5px;color:var(--ink2);margin:14px 0 5px;
  font-weight:500}
.chk{display:flex;align-items:center;gap:9px;padding:5px 0;color:var(--ink2);
  font-size:13.5px;cursor:pointer}
.chk input{accent-color:var(--accent);width:15px;height:15px;cursor:pointer;
  flex:0 0 auto}
.chk:hover{color:var(--ink)}

/* small data tables */
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:4px 0;color:var(--ink2);vertical-align:baseline}
td.n{text-align:right;color:var(--ink);white-space:nowrap;padding-left:8px}
.meter{height:3px;background:var(--line);border-radius:3px;margin:4px 0 9px;
  position:relative;overflow:hidden}
.meter i{position:absolute;inset:0 auto 0 0;border-radius:3px;display:block}
.good{color:#5f9c70}.bad{color:#b8622f}.flat{color:var(--ink3)}
:root[data-theme="dark"] .good{color:#8fc79e}
:root[data-theme="dark"] .bad{color:#d98b6d}
.evrow{display:flex;justify-content:space-between;font-size:13.5px;align-items:baseline}
.evrow b{font-weight:500;color:var(--ink)}

/* ---------- stage ---------- */
#stage{flex:1;position:relative;min-width:0;overflow:hidden}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block;
  cursor:grab;touch-action:none}
canvas.grabbing{cursor:grabbing}
canvas:focus-visible{outline:2px solid var(--accent2);outline-offset:-2px}

.float{background:var(--veil);border:1px solid var(--line);border-radius:8px}
#legend{position:absolute;left:20px;top:18px;font-size:13px;color:var(--ink2);
  padding:11px 14px;pointer-events:none;max-width:255px}
#legend h3{font:600 10.5px var(--sans);text-transform:uppercase;letter-spacing:1.2px;
  color:var(--ink3);margin:0 0 8px}
#legend div{display:flex;align-items:center;gap:8px;padding:2px 0;line-height:1.35}
#legend svg{flex:0 0 12px}

#hud{position:absolute;left:20px;bottom:18px;font-size:12.5px;color:var(--ink3);
  pointer-events:none;letter-spacing:.1px;max-width:56%}
#hud b{color:var(--ink2);font-weight:600}

#zoomer{position:absolute;right:20px;bottom:18px;display:flex;align-items:center;
  gap:2px;padding:4px}
#zoomer button{border:0;background:transparent;padding:5px 9px;font-size:15px;
  line-height:1;color:var(--ink2)}
#zoomer button:hover{background:var(--panel2);color:var(--ink)}
#zoomer .pct{font-size:12px;color:var(--ink3);min-width:46px;text-align:center}

#tip{position:absolute;pointer-events:none;z-index:6;display:none;
  padding:10px 13px;max-width:310px;box-shadow:var(--shadow)}
#tip .t{font:400 15px/1.3 var(--serif);color:var(--ink)}
#tip .m{color:var(--ink3);font-size:12.5px;margin-top:4px}
#tip .s{color:var(--accent);font-size:12.5px;margin-top:5px;font-weight:600}

/* First-run explanation. A DH reader arriving cold needs to know what the dots
   are and what the sliders do before anything else on the page makes sense. */
#intro{position:absolute;inset:0;z-index:20;display:flex;align-items:center;
  justify-content:center;background:var(--scrim);padding:24px}
#intro .card{max-width:620px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;padding:30px 34px 26px;box-shadow:var(--shadow);
  max-height:100%;overflow-y:auto}
#intro h2{font:400 27px/1.2 var(--serif);margin:0 0 4px;color:var(--ink)}
#intro .lede{color:var(--ink2);font-size:15.5px;line-height:1.6;margin:0 0 18px}
#intro p{color:var(--ink2);font-size:14.5px;line-height:1.65;margin:0 0 13px}
#intro b{color:var(--ink);font-weight:600}
#intro .grid{display:grid;grid-template-columns:1fr 1fr;gap:9px 20px;
  margin:16px 0 18px;padding:15px 0;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line)}
#intro .grid div{font-size:13.5px;color:var(--ink2);line-height:1.4}
#intro .grid b{display:block;color:var(--ink);font-size:13.5px}
#intro .go{padding:9px 18px;font-size:14.5px;border-color:var(--accent);
  color:var(--accent)}
#intro .skip{color:var(--ink3);font-size:13px;margin-left:12px}

/* ---------- detail panel ---------- */
#detail{position:absolute;top:0;right:0;bottom:0;width:404px;z-index:7;
  background:var(--panel);border-left:1px solid var(--line);overflow-y:auto;
  transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);
  overscroll-behavior:contain}
#detail.open{transform:none}
.dhead{padding:20px 22px 16px;border-bottom:1px solid var(--line);position:sticky;
  top:0;background:var(--panel);z-index:2}
.dhead h2{font:400 21px/1.25 var(--serif);margin:0 36px 0 0;color:var(--ink)}
.dhead .meta{color:var(--ink3);font-size:12.5px;margin-top:8px;line-height:1.5}
.dclose{position:absolute;top:17px;right:17px;padding:3px 9px;font-size:15px}
.dsec{padding:17px 22px;border-bottom:1px solid var(--line)}
.dsec h3{font:600 11.5px var(--sans);text-transform:uppercase;letter-spacing:1.2px;
  color:var(--ink2);margin:0 0 10px;display:flex;justify-content:space-between;
  align-items:baseline;gap:8px}
.dsec h3 em{font:400 12px var(--sans);text-transform:none;letter-spacing:0;
  color:var(--ink3);flex:0 0 auto}
.chip{display:inline-block;border:1px solid var(--line);background:var(--panel2);
  color:var(--ink2);border-radius:12px;padding:3px 11px;margin:0 5px 6px 0;
  font-size:12.5px}
.chip.tool{border-color:var(--toolline);color:var(--ph)}
.chip.topic{border-color:var(--topicline);color:var(--accent2)}
ol.steps{margin:0;padding:0;list-style:none;counter-reset:s}
ol.steps li{counter-increment:s;position:relative;padding:0 0 13px 28px;
  border-left:1px solid var(--line);margin-left:9px}
ol.steps li:last-child{border-left-color:transparent;padding-bottom:0}
ol.steps li::before{content:counter(s);position:absolute;left:-10px;top:0;
  width:19px;height:19px;border-radius:50%;background:var(--panel2);
  border:1px solid var(--line);color:var(--ink3);font-size:10.5px;
  display:flex;align-items:center;justify-content:center}
ol.steps .st{color:var(--ink);font-size:13.5px;line-height:1.4}
ol.steps .sm{color:var(--ink3);font-size:12.5px;margin-top:2px;font-style:italic}
.nb{display:block;width:100%;text-align:left;border:1px solid var(--line);
  background:var(--panel2);border-radius:8px;padding:11px 13px;margin:0 0 8px;
  cursor:pointer;transition:border-color .12s,background .12s}
.nb:hover{border-color:var(--accent)}
.nb .t{color:var(--ink);font-size:13.5px;line-height:1.4;margin-bottom:7px}
.nb .r{display:flex;align-items:center;gap:9px;color:var(--ink3);font-size:12px}
.nb .pct{color:var(--accent);font-weight:600;font-size:12.5px;min-width:34px}
.nb .sh{color:var(--ink3);font-size:12px;margin-top:6px;line-height:1.45}
.nb .sh b{color:var(--ink2);font-weight:600}
.sim{flex:1;height:3px;background:var(--line);border-radius:3px;overflow:hidden}
.sim i{display:block;height:3px;background:var(--accent);border-radius:3px}
a{color:var(--accent2);text-decoration:none;
  border-bottom:1px solid var(--linkline)}
a:hover{border-bottom-color:var(--accent2)}
.warn{background:var(--tint);border:1px solid var(--tintline);
  color:var(--accent);border-radius:7px;padding:10px 12px;font-size:12.5px;
  margin:10px 0 0;line-height:1.5}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
</style>
<div id="app">
<div id="rail">
  <div class="masthead">
    <div class="top">
      <h1>Workflow Galaxy</h1>
      <div class="prefs">
        <button id="theme" title="Light or dark" aria-label="Switch theme">&#9681;</button>
        <button id="typeup" title="Larger text" aria-label="Larger text">A&#8202;+</button>
        <button id="help" title="What am I looking at?" aria-label="Help">?</button>
      </div>
    </div>
    <p id="masthead-sub"></p>
  </div>

  <section id="sec-w">
    <div class="sechead"><h2>What makes two workflows alike</h2><span class="caret">&#9660;</span></div>
    <div class="body">
      <p class="hint">Two projects can resemble each other in more than one way.
      Decide which ways count, and by how much. <em>Everything on the page follows
      these settings.</em></p>
      <div id="weights"></div>
      <div id="wwarn"></div>
      <label class="fieldlabel">Or start from a question</label>
      <div class="btns" style="margin-top:0">
        <button id="wReset">A bit of everything</button>
        <button data-preset="method">Does the same things</button>
        <button data-preset="tool">Uses the same software</button>
        <button data-preset="topic">Studies the same subject</button>
        <button data-preset="flow">Proceeds the same way</button>
      </div>
    </div>
  </section>

  <section id="sec-p">
    <div class="sechead"><h2>Where the dots sit</h2><span class="caret">&#9660;</span></div>
    <div class="body">
      <select id="posMode" aria-label="layout"></select>
      <p class="aside">Each arrangement places workflows so that similar ones fall
      near each other. Distances between distant groups mean nothing — read which
      things touch, not how far apart two clusters are.</p>
      <div class="btns"><button id="relayout" class="primary">Rearrange for my settings</button></div>
    </div>
  </section>

  <section id="sec-c">
    <div class="sechead"><h2>How the map is drawn</h2><span class="caret">&#9660;</span></div>
    <div class="body">
      <label class="fieldlabel" for="colour">colour</label>
      <select id="colour">
        <option value="src">source</option>
        <option value="cluster">cluster in this layout</option>
        <option value="goal">dominant TaDiRAH goal</option>
        <option value="nsteps">number of steps</option>
        <option value="msrc">declared vs inferred methods</option>
        <option value="lang">language</option>
      </select>
      <label class="fieldlabel" for="labels">labels</label>
      <select id="labels">
        <option value="auto">selection, neighbours and ETKAD</option>
        <option value="sel">selection and neighbours only</option>
        <option value="zoom">only what fits when zoomed in</option>
        <option value="off">none</option>
      </select>
      <label class="fieldlabel" for="links">strongest links</label>
      <select id="links">
        <option value="120">show the 120 closest pairs</option>
        <option value="300">show the 300 closest pairs</option>
        <option value="0">hide</option>
      </select>
      <p class="aside">A dot's size is how many methods the workflow declares.
      Its shape is always its source, so the map still reads if you cannot
      distinguish the colours. The threads join the most similar pairs
      <em>under your current settings</em>, and re-draw as you move a slider.
      <a href="how_it_works.html" target="_blank" rel="noopener">How similarity is
      calculated &rarr;</a></p>
    </div>
  </section>

  <section id="sec-f">
    <div class="sechead"><h2>Which workflows to show</h2><span class="caret">&#9660;</span></div>
    <div class="body">
      <div id="filters"></div>
      <label class="fieldlabel" for="q">search titles, methods, software, subjects</label>
      <input type="text" id="q" placeholder="e.g. maps, OCR, folklore, OpenRefine&hellip;"
             autocomplete="off">
    </div>
  </section>

  <section id="sec-e" class="closed">
    <div class="sechead"><h2>Can the map be trusted?</h2><span class="caret">&#9660;</span></div>
    <div class="body" id="evalBox"></div>
  </section>

  <section id="sec-s" class="closed">
    <div class="sechead"><h2>When things happen in a project</h2><span class="caret">&#9660;</span></div>
    <div class="body" id="shapeBox"></div>
  </section>

  <section id="sec-t" class="closed">
    <div class="sechead"><h2>What tends to follow what</h2><span class="caret">&#9660;</span></div>
    <div class="body" id="flowBox"></div>
  </section>

  <section id="sec-x" class="closed">
    <div class="sechead"><h2>Take it away</h2><span class="caret">&#9660;</span></div>
    <div class="body">
      <div class="btns" style="margin-top:0">
        <button id="png">Save picture</button>
        <button id="csv">Download table</button>
        <button id="link">Copy link to this view</button>
      </div>
      <p class="aside" id="stamp"></p>
    </div>
  </section>
</div>

<div id="stage">
  <canvas id="cv" tabindex="0" role="img" aria-label="Map of workflows"></canvas>
  <div id="legend" class="float"></div>
  <div id="hud"></div>
  <div id="zoomer" class="float">
    <button id="zout" title="Zoom out" aria-label="Zoom out">&minus;</button>
    <span class="pct" id="zpct">100%</span>
    <button id="zin" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="zfit" title="Fit to view (F)" aria-label="Fit to view">&#9974;</button>
  </div>
  <div id="tip" class="float" role="tooltip"></div>
  <aside id="detail" aria-label="workflow detail"></aside>
  <div id="intro">
    <div class="card">
      <h2>What am I looking at?</h2>
      <p class="lede">Every dot is one research workflow — a project written down as
      the steps it went through. There are 240 of them, from three places.</p>
      <p>They are drawn so that <b>workflows resembling each other sit close
      together</b>. Nothing here knows what any project is <em>about</em> in the way
      a reader would. It only knows what each one declared: the methods it names,
      the software it mentions, the subjects it is filed under, the order of its
      steps.</p>
      <p>That is why the panel on the left is the important part.
      <b>You decide what "resembling" means</b> — the same operations, the same
      software, the same subject, or the same shape of process — and the map, the
      threads between dots and every suggested neighbour follow your choice.</p>
      <div class="grid">
        <div><b>SSH Open Marketplace</b>108 European DH workflows</div>
        <div><b>Programming Historian</b>119 tutorial lessons</div>
        <div><b>ETKAD</b>13 Estonian workflows (English versions), labelled by default</div>
        <div><b>Click a dot</b>to read it and see what it resembles</div>
      </div>
      <p style="color:var(--ink3);font-size:13.5px">Drag to move the map, scroll to
      zoom, press <b>F</b> to fit it back in view. This panel is always available
      from the <b>?</b> button. If you want to know exactly how &ldquo;resembling&rdquo;
      is calculated, there is
      <a href="how_it_works.html" target="_blank" rel="noopener">a technical
      explanation with a worked example</a>.</p>
      <div style="margin-top:18px">
        <button class="go" id="introGo">Open the map</button>
        <span class="skip">or press Escape</span>
      </div>
    </div>
  </div>
</div>
</div>
<script>
const D = __DATA__;
const NL = String.fromCharCode(10);
const W = D.workflows, N = W.length, FAC = D.facets;

/* Okabe-Ito: colourblind-safe. Source is also encoded as shape, so the map
   survives greyscale printing and every kind of colour vision. Okabe-Ito was
   designed against white, so the dark theme uses the palette as published and
   the light theme darkens it to hold 4.5:1 against paper. */
const SHAPE = {sshomp:"circle",  ph:"triangle", etkad:"diamond"};
const SRCNAME = {sshomp:"SSH Open Marketplace", ph:"Programming Historian", etkad:"ETKAD"};
const PALS = {
  dark:{
    src:{sshomp:"#56b4e9", ph:"#e69f00", etkad:"#cc79a7"},
    pal:["#56b4e9","#e69f00","#009e73","#cc79a7","#0072b2","#d55e00","#ded06a",
         "#8ea4c8","#b08968","#7fb3a5","#c58fb0","#6f9ec9","#d8a05a","#9dbf8e"],
    goal:{Capture:"#56b4e9", Discovery:"#009e73", Enrichment:"#e69f00",
      Storage:"#8ea4c8", Analysis:"#cc79a7", Interpretation:"#d55e00",
      Creation:"#0072b2", Dissemination:"#7fb3a5"},
    none:"#4d4b52", link:"150,150,170", thread:.30,
    label:"#b9b7b4", labelSel:"#f4f2ee", ring:"#f4f2ee", box:"21,21,26"},
  light:{
    src:{sshomp:"#2f7fb5", ph:"#b06d00", etkad:"#a94c81"},
    pal:["#2f7fb5","#b06d00","#00775a","#a94c81","#00568b","#a84500","#8a7c1e",
         "#5c729a","#7d5a3c","#4d8477","#96608a","#3f6d97","#a06f2c","#5e7f52"],
    goal:{Capture:"#2f7fb5", Discovery:"#00775a", Enrichment:"#b06d00",
      Storage:"#5c729a", Analysis:"#a94c81", Interpretation:"#a84500",
      Creation:"#00568b", Dissemination:"#4d8477"},
    none:"#b3aea4", link:"70,64,56", thread:.36,
    label:"#55524d", labelSel:"#1a1815", ring:"#1a1815", box:"250,248,244"},
};
let theme="dark", P=PALS.dark;
const srcCol  = s => P.src[s] || P.none;
const palCol  = i => P.pal[((i % P.pal.length) + P.pal.length) % P.pal.length];
const goalCol = g => P.goal[g] || P.none;

let wgt = Object.assign({}, D.default_w);
let posMode = "blend", colour = "src", query = "";
let labelMode = "auto", linkCount = 120;
let sel = null, custom = null, topPairs = null;
const show = {sshomp:true, ph:true, etkad:true, stepsOnly:false, taggedOnly:false};

/* ================= similarity, recomputed live ================= */
function facetSim(f){
  const rows = D.vectors[f].rows, S = new Float32Array(N*N);
  const maps = rows.map(r=>{const m=new Map(); for(const p of r) m.set(p[0],p[1]); return m;});
  const norms = new Float32Array(N);
  for(let i=0;i<N;i++){let s=0; for(const v of maps[i].values()) s+=v*v; norms[i]=Math.sqrt(s)||1;}
  for(let i=0;i<N;i++) for(let j=i+1;j<N;j++){
    let dot=0; const a=maps[i], b=maps[j];
    const small = a.size<b.size?a:b, big = a.size<b.size?b:a;
    for(const [k,v] of small){ const u=big.get(k); if(u!==undefined) dot+=v*u; }
    const s=dot/(norms[i]*norms[j]); S[i*N+j]=s; S[j*N+i]=s;
  }
  return S;
}
const SIM={}; for(const f of FAC) SIM[f]=facetSim(f);

let BS=null, anyWeight=true;
function blended(){
  const S=new Float32Array(N*N); let tot=0;
  for(const f of FAC){ const w=wgt[f]; if(w<=0) continue; tot+=w;
    const A=SIM[f]; for(let k=0;k<N*N;k++) S[k]+=w*A[k]; }
  anyWeight = tot>0;
  if(tot>0) for(let k=0;k<N*N;k++) S[k]/=tot;
  return S;
}
/* Neighbours rank over the whole corpus, not over what happens to be filtered
   in. Filtering is a view of the map; it should not silently rewrite an
   answer. Filtered-out neighbours are marked instead of removed. */
function neighbours(i,k){
  const out=[];
  for(let j=0;j<N;j++) if(j!==i) out.push([j,BS[i*N+j]]);
  out.sort((a,b)=>b[1]-a[1]);
  return out.slice(0,k).filter(p=>p[1]>0.001);
}
function why(i,j){
  return FAC.filter(f=>wgt[f]>0).map(f=>[f,SIM[f][i*N+j]])
    .filter(x=>x[1]>0.02).sort((a,b)=>b[1]-a[1]);
}
function sharedFeatures(i,j,f){
  const a=new Set(D.vectors[f].rows[i].map(x=>x[0])), v=D.vectors[f].vocab;
  return D.vectors[f].rows[j].filter(x=>a.has(x[0])).map(x=>v[x[0]]);
}
function hasFeatures(i){
  for(const f of FAC) if(wgt[f]>0 && D.vectors[f].rows[i].length) return true;
  return false;
}
/* The most similar pairs in the whole corpus under the current weights. This is
   what makes a slider visibly do something when nothing is selected: without it,
   dragging changes only the numbers in the readout, and the map looks frozen. */
function strongestPairs(k){
  if(!anyWeight || k<=0) return [];
  const out=[];
  for(let i=0;i<N;i++) for(let j=i+1;j<N;j++){
    const s=BS[i*N+j];
    if(s>0.05) out.push([i,j,s]);
  }
  out.sort((a,b)=>b[2]-a[2]);
  return out.slice(0,k);
}

/* ================= custom layout ================= */
function customLayout(iters,warm){
  const pts=new Float64Array(N*2);
  /* Seed from the blended embedding, never from scratch. Seeding from
     `D.layouts[posMode]` was a bug: by the time this ran posMode was already
     "custom", so there was no seed and every run started from a different
     spiral. `warm` continues from the positions already on screen, which is what
     keeps a slider drag a nudge rather than a jump. */
  const seed=warm||(D.layouts.blend||D.layouts[FAC[0]]).xy;
  for(let i=0;i<N;i++){ pts[i*2]=seed[i][0]; pts[i*2+1]=seed[i][1]; }
  const dist=new Float32Array(N*N);
  for(let k=0;k<N*N;k++) dist[k]=(1-BS[k])*8;
  for(let it=0;it<iters;it++){
    const nx=new Float64Array(N*2), ws=new Float64Array(N);
    for(let i=0;i<N;i++) for(let j=0;j<N;j++){
      if(i===j) continue;
      const dx=pts[i*2]-pts[j*2], dy=pts[i*2+1]-pts[j*2+1];
      const d=Math.hypot(dx,dy)||1e-6, t=dist[i*N+j], w=1/(t*t+0.05);
      nx[i*2]+=w*(pts[j*2]+t*dx/d); nx[i*2+1]+=w*(pts[j*2+1]+t*dy/d); ws[i]+=w;
    }
    for(let i=0;i<N;i++){ pts[i*2]=nx[i*2]/ws[i]; pts[i*2+1]=nx[i*2+1]/ws[i]; }
  }
  const xy=[]; for(let i=0;i<N;i++) xy.push([pts[i*2],pts[i*2+1]]);
  return xy;
}

/* ================= view ================= */
const cv=document.getElementById("cv"), ctx=cv.getContext("2d");
const detail=document.getElementById("detail");
let vw=0,vh=0,scale=1,baseScale=1,ox=0,oy=0;
let dragging=false,moved=false,lx=0,ly=0,hover=null,raf=0;
const PANEL=376;
function inset(){ return detail.classList.contains("open") ? PANEL : 0; }

let XY=null;
function coords(){
  if(posMode==="custom"){ if(!custom) custom=customLayout(70); return custom; }
  return (D.layouts[posMode]||D.layouts.blend).xy;
}
function fit(){
  XY=coords();
  const xs=XY.map(p=>p[0]).slice().sort((a,b)=>a-b);
  const ys=XY.map(p=>p[1]).slice().sort((a,b)=>a-b);
  const q=(arr,f)=>arr[Math.max(0,Math.min(arr.length-1,Math.floor(arr.length*f)))];
  const x0=q(xs,.02),x1=q(xs,.98),y0=q(ys,.02),y1=q(ys,.98);
  const availW=Math.max(120,vw-inset()-56), availH=Math.max(120,vh-96);
  scale=Math.min(availW/((x1-x0)||1), availH/((y1-y0)||1));
  baseScale=scale;
  ox=(vw-inset())/2 - scale*(x0+x1)/2;
  oy=vh/2 - scale*(y0+y1)/2;
}
function sx(i){return XY[i][0]*scale+ox}
function sy(i){return XY[i][1]*scale+oy}
const zoom=()=>scale/baseScale;

function visible(i){
  const w=W[i];
  if(!show[w.src]) return false;
  if(show.stepsOnly && w.nsteps<2) return false;
  if(show.taggedOnly && w.method_src!=="declared") return false;
  if(query){
    const hay=(w.title+" "+w.methods.join(" ")+" "+w.tools.join(" ")+" "+
               w.topics.join(" ")+" "+w.goals.join(" ")).toLowerCase();
    if(!hay.includes(query)) return false;
  }
  return true;
}
function nodeColour(i){
  const w=W[i];
  if(colour==="src") return srcCol(w.src);
  if(colour==="cluster"){const L=D.layouts[posMode]||D.layouts.blend;
    const c=L.c?L.c[i]:-1; return c<0?P.none:palCol(c);}
  if(colour==="goal") return goalCol(w.goals[0]);
  if(colour==="nsteps"){const t=Math.min(1,w.nsteps/16);
    return theme==="light"
      ? "rgb("+Math.round(60+110*t)+","+Math.round(95+40*t)+","+Math.round(150-60*t)+")"
      : "rgb("+Math.round(70+150*t)+","+Math.round(105+65*t)+","+Math.round(190-70*t)+")";}
  if(colour==="msrc") return w.method_src==="declared"?P.src.sshomp:P.goal.Interpretation;
  if(colour==="lang") return w.lang==="Estonian"?P.src.etkad:P.src.sshomp;
  return P.src.sshomp;
}
function nodeColourFor(nsteps){
  const t=Math.min(1,nsteps/16);
  return theme==="light"
    ? "rgb("+Math.round(60+110*t)+","+Math.round(95+40*t)+","+Math.round(150-60*t)+")"
    : "rgb("+Math.round(70+150*t)+","+Math.round(105+65*t)+","+Math.round(190-70*t)+")";
}
/* Radius grows sub-linearly with zoom. Fixed-radius dots turn a zoomed-in map
   into a few specks adrift in emptiness. */
function radius(i){
  const base=3.1+Math.sqrt(W[i].methods.length)*1.15;
  return base*Math.min(2.1,Math.max(.8,Math.pow(zoom(),.42)));
}
function shapePath(i,x,y,r){
  const s=SHAPE[W[i].src];
  ctx.beginPath();
  if(s==="circle") ctx.arc(x,y,r,0,6.2832);
  else if(s==="triangle"){const h=r*1.28;
    ctx.moveTo(x,y-h); ctx.lineTo(x+h*.93,y+h*.66); ctx.lineTo(x-h*.93,y+h*.66); ctx.closePath();}
  else {const d=r*1.3;
    ctx.moveTo(x,y-d); ctx.lineTo(x+d,y); ctx.lineTo(x,y+d); ctx.lineTo(x-d,y); ctx.closePath();}
}

function schedule(){ if(!raf) raf=requestAnimationFrame(()=>{raf=0; draw();}); }

/* Rectangles of the floating UI, in canvas coordinates, so label placement can
   treat them as occupied space. */
function obstacles(){
  const cr=cv.getBoundingClientRect(), out=[];
  for(const id of ["legend","hud","zoomer","onboard"]){
    const el=document.getElementById(id);
    if(!el || el.style.display==="none" || !el.offsetWidth) continue;
    const r=el.getBoundingClientRect();
    out.push({x:r.left-cr.left-6, y:r.top-cr.top-6, w:r.width+12, h:r.height+12});
  }
  return out;
}

function draw(){
  if(!XY) XY=coords();
  ctx.clearRect(0,0,vw,vh);
  const nb = sel!==null ? new Map(neighbours(sel,8)) : null;
  const pad=90;
  const onscreen=i=>{const x=sx(i),y=sy(i);
    return x>-pad && x<vw+pad && y>-pad && y<vh+pad;};

  // Similarity network, drawn under everything. Recomputed whenever the weights
  // move, so the structure visibly re-wires as you drag.
  if(sel===null && linkCount>0){
    if(!topPairs) topPairs=strongestPairs(linkCount);
    ctx.lineWidth=0.8;
    for(const [i,j,s] of topPairs){
      if(!visible(i)||!visible(j)) continue;
      if(!onscreen(i)&&!onscreen(j)) continue;
      ctx.strokeStyle="rgba("+P.link+","+Math.min(P.thread,s*.42).toFixed(3)+")";
      ctx.beginPath(); ctx.moveTo(sx(i),sy(i)); ctx.lineTo(sx(j),sy(j)); ctx.stroke();
    }
  }
  if(sel!==null && nb){
    for(const [j,s] of nb){
      const g=ctx.createLinearGradient(sx(sel),sy(sel),sx(j),sy(j));
      g.addColorStop(0,"rgba(224,164,88,"+Math.min(.85,.25+s).toFixed(2)+")");
      g.addColorStop(1,"rgba(224,164,88,"+Math.min(.45,s*.6).toFixed(2)+")");
      ctx.strokeStyle=g; ctx.lineWidth=Math.max(.7,s*3.4);
      ctx.beginPath(); ctx.moveTo(sx(sel),sy(sel)); ctx.lineTo(sx(j),sy(j)); ctx.stroke();
    }
  }
  for(let i=0;i<N;i++){
    // An explicit selection always draws, even when a filter or search would
    // hide it. Otherwise the panel describes a workflow whose links converge on
    // empty space.
    if((!visible(i) && i!==sel) || !onscreen(i)) continue;
    const blank=!hasFeatures(i);
    const focus = sel===null || i===sel || (nb&&nb.has(i));
    ctx.globalAlpha = blank?0.12:(focus?0.94:0.17);
    ctx.fillStyle=nodeColour(i);
    shapePath(i,sx(i),sy(i),radius(i)); ctx.fill();
    if(i===sel){ ctx.globalAlpha=1; ctx.strokeStyle="#f2efe9"; ctx.lineWidth=1.8;
      shapePath(i,sx(i),sy(i),radius(i)+3.2); ctx.stroke(); }
    else if(i===hover){ ctx.globalAlpha=.85; ctx.strokeStyle="#e6e4e0"; ctx.lineWidth=1.2;
      shapePath(i,sx(i),sy(i),radius(i)+2.4); ctx.stroke(); }
  }
  ctx.globalAlpha=1;

  /* Labels, viewport-first. The previous version ranked all 237 nodes, sliced to
     70, and only then dropped the off-screen ones, so zooming in spent the whole
     budget on things nobody could see. Candidates are now restricted to what is
     actually visible before any ranking happens, and the budget grows with zoom
     instead of every label appearing at once past a hard threshold. */
  const z=zoom(), budget=Math.round(Math.min(90, 16+34*Math.log2(1+z)));
  const cands=[];
  for(let i=0;i<N;i++){
    if(labelMode==="off") break;
    if(!visible(i)||!onscreen(i)) continue;
    if(i!==sel && !hasFeatures(i)) continue;
    let pr;
    if(i===sel) pr=1e6;
    else if(nb&&nb.has(i)) pr=1e5+nb.get(i)*100;
    // ETKAD is labelled unconditionally in `auto` — that is the whole point of
    // the mode — but it is only a default, and `sel`/`zoom`/`off` turn it off.
    else if(W[i].src==="etkad" && labelMode==="auto") pr=1e4;
    else if(z>=1.25 && labelMode!=="sel") pr=W[i].methods.length*10+W[i].nsteps;
    else continue;
    cands.push([i,pr]);
  }
  cands.sort((a,b)=>b[1]-a[1]);
  ctx.font='13px '+getComputedStyle(document.body).fontFamily;
  ctx.textBaseline="middle";
  ctx.lineJoin="round";
  /* Seed the collision list with the on-canvas furniture so labels never end up
     underneath the legend, the readout or the zoom control. */
  const boxes=obstacles();
  const maxChars = z>2 ? 60 : 40;
  for(const c of cands.slice(0,budget)){
    const i=c[0];
    let t=W[i].title;
    if(t.length>maxChars) t=t.slice(0,maxChars-1).trimEnd()+"…";
    const tw=ctx.measureText(t).width;
    const y=sy(i), right=vw-inset()-6;
    // Flip to the left of the node when the label would run off the right edge —
    // otherwise every node near the right margin goes silently unlabelled.
    let x=sx(i)+radius(i)+7;
    if(x+tw+3>right) x=sx(i)-radius(i)-7-tw;
    const b={x:x-3,y:y-9,w:tw+6,h:18};
    if(b.x+b.w>right || b.x<4 || b.y<4 || b.y+b.h>vh-6) continue;
    let clash=false;
    for(const o of boxes){
      if(b.x<o.x+o.w && b.x+b.w>o.x && b.y<o.y+o.h && b.y+b.h>o.y){clash=true;break;}
    }
    if(clash) continue;
    boxes.push(b);
    // A halo in the background colour rather than a filled plate: it keeps the
    // dots and threads underneath visible, which a solid box punches out.
    ctx.strokeStyle="rgba("+P.box+",.92)"; ctx.lineWidth=3.5;
    ctx.strokeText(t,x,y);
    ctx.fillStyle = i===sel ? P.labelSel
      : (nb&&nb.has(i)) ? P.src.ph
      : (W[i].src==="etkad") ? P.src.etkad : P.label;
    ctx.fillText(t,x,y);
  }

  let vis=0, blanks=0;
  for(let i=0;i<N;i++) if(visible(i)){vis++; if(!hasFeatures(i)) blanks++;}
  const on=FAC.filter(f=>wgt[f]>0)
    .sort((a,b)=>wgt[b]-wgt[a]).map(f=>FNAME[f].toLowerCase());
  document.getElementById("hud").innerHTML =
    "<b>"+vis+"</b> of "+N+" workflows shown" +
    (blanks?' &middot; '+blanks+" faded — nothing recorded for these settings":"") +
    ' &middot; alike by ' + (on.length? on.join(", ") : "nothing yet");
  document.getElementById("zpct").textContent=Math.round(z*100)+"%";
}

/* ================= rail ================= */
/* Plain names for a reading audience. The internal keys stay as they are; only
   what the page says changes. "flow" and "material" in particular meant nothing
   to anyone who had not read the code. */
const FNAME={method:"Methods", goal:"Kind of work", tool:"Software",
  topic:"Subject", material:"Materials", flow:"Order of steps", text:"Wording"};
const FDESC={
  method:"the research operations it names — annotating, geo-referencing, topic modelling",
  goal:"the same operations grouped into eight broad kinds of work",
  tool:"the programs and platforms mentioned by name",
  topic:"what the project is about — its keywords and discipline",
  material:"the formats and media it works on (few workflows record this)",
  flow:"the order it proceeds in, ignoring what it is about",
  text:"the language of its title and description"};
/* 0 to 1.5 in tenths is a false precision for a judgement like this; the value
   is shown in words instead, and only the shown word has to be understood. */
function wgtWord(v){
  return v<=0 ? "ignore" : v<0.35 ? "a little" : v<0.75 ? "somewhat"
       : v<1.15 ? "a lot" : "above all";
}
function buildWeights(){
  document.getElementById("weights").innerHTML = FAC.map(f=>
    '<div class="fac'+(wgt[f]>0?"":" off")+'" data-fac="'+f+'">'+
      '<div class="top"><span class="name">'+FNAME[f]+'</span>'+
      '<span class="val">'+wgtWord(wgt[f])+'</span></div>'+
      '<p class="desc">'+FDESC[f]+'</p>'+
      '<input type="range" min="0" max="1.5" step="0.1" value="'+wgt[f]+
      '" data-f="'+f+'" aria-label="How much '+FNAME[f]+' counts"></div>').join("");
  document.querySelectorAll('#weights input').forEach(el=>{
    el.oninput=()=>{
      const f=el.dataset.f; wgt[f]=+el.value;
      const box=el.closest(".fac");
      box.querySelector(".val").textContent=wgtWord(wgt[f]);
      box.classList.toggle("off", wgt[f]<=0);
      recompute();
    };
  });
}
let relayoutTimer=0;
function recompute(){
  BS=blended(); topPairs=null;
  document.getElementById("wwarn").innerHTML = anyWeight ? "" :
    '<div class="warn">Every aspect is at zero, so nothing can be similar to '+
    'anything. Raise at least one.</div>';
  if(sel!==null) renderDetail(sel);
  schedule(); saveURL();
  // When the map is already showing a custom layout, follow the weights. The
  // refine is warm-started from the current positions, so dragging a slider
  // nudges the map rather than throwing it into a new arrangement.
  if(posMode==="custom"){
    clearTimeout(relayoutTimer);
    relayoutTimer=setTimeout(()=>{ custom=customLayout(40,custom); XY=custom; draw(); },200);
  }
}
function setW(o){ for(const f of FAC) wgt[f]=o[f]||0; buildWeights(); recompute(); }

function legend(){
  const L=document.getElementById("legend");
  const dot=(col,shape)=>{
    if(shape==="triangle") return '<svg width="12" height="12"><polygon points="6,1 11.5,11 .5,11" fill="'+col+'"/></svg>';
    if(shape==="diamond")  return '<svg width="12" height="12"><polygon points="6,.5 11.5,6 6,11.5 .5,6" fill="'+col+'"/></svg>';
    return '<svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="'+col+'"/></svg>';
  };
  let title="Where it comes from", rows="";
  if(colour==="src") rows=["sshomp","ph","etkad"].map(s=>
    '<div>'+dot(srcCol(s),SHAPE[s])+SRCNAME[s]+'</div>').join("");
  else if(colour==="goal"){ title="Its main kind of work";
    rows=D.goal_order.map(g=>'<div>'+dot(goalCol(g),"circle")+g+'</div>').join("")
      + '<div>'+dot(P.none,"circle")+'no methods recorded</div>'; }
  else if(colour==="msrc"){ title="Where the methods came from";
    rows='<div>'+dot(P.src.sshomp,"circle")+'a person tagged them</div>'+
         '<div>'+dot(P.goal.Interpretation,"circle")+'read out of the text</div>'; }
  else if(colour==="lang"){ title="Language of the record";
    rows='<div>'+dot(P.src.sshomp,"circle")+'English</div>'+
         '<div>'+dot(P.src.etkad,"circle")+'Estonian</div>'; }
  else if(colour==="nsteps"){ title="How many steps it records";
    rows='<div>'+dot(nodeColourFor(1),"circle")+'few</div>'+
         '<div>'+dot(nodeColourFor(16),"circle")+'many (16 or more)</div>'; }
  else if(colour==="cluster"){ const L2=D.layouts[posMode]||D.layouts.blend;
    title="Groups the map found by itself";
    const ks=Object.keys(L2.labels||{}).slice(0,7);
    rows=ks.map(k=>'<div>'+dot(palCol(+k),"circle")+
      '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+
      esc(L2.labels[k])+'</span></div>').join("")||'<div>no groups in this view</div>'; }
  const shapes = colour==="src" ? "" :
    '<div style="margin-top:9px;padding-top:8px;border-top:1px solid var(--line);'+
    'color:var(--ink3);font-size:12px">'+
    ["sshomp","ph","etkad"].map(s=>dot(P.none,SHAPE[s])+" "+
      (s==="sshomp"?"Marketplace":s==="ph"?"Prog. Hist.":"ETKAD")).join(" &nbsp;")+'</div>';
  L.innerHTML='<h3>'+title+'</h3>'+rows+shapes;
}

function buildRail(){
  document.getElementById("masthead-sub").innerHTML =
    N+" research workflows from Estonia, the SSH Open Marketplace and Programming "+
    "Historian &mdash; and a way to ask which of them resemble each other, "+
    "and in what respect.";

  document.querySelectorAll(".sechead").forEach(h=>{
    h.onclick=()=>h.parentElement.classList.toggle("closed");
  });

  const pm=document.getElementById("posMode");
  pm.innerHTML=Object.keys(D.layouts).map(k=>'<option value="'+k+'">'+
    (k==="blend"?"Blended (default weights)":k.charAt(0).toUpperCase()+k.slice(1)+" only")+
    '</option>').join("")+'<option value="custom">Custom — my exact weights</option>';
  pm.value=posMode;
  pm.onchange=()=>{posMode=pm.value;
    if(posMode==="custom" && !custom) custom=customLayout(110);
    fit(); schedule(); legend(); saveURL();};
  const rl=document.getElementById("relayout");
  rl.onclick=()=>{
    rl.disabled=true; rl.textContent="Computing…";
    setTimeout(()=>{
      custom=customLayout(110);
      posMode="custom"; pm.value="custom"; fit(); draw();
      rl.disabled=false; rl.textContent="Recompute for my weights"; saveURL();
    },30);
  };
  document.getElementById("colour").onchange=e=>{
    colour=e.target.value; legend(); schedule(); saveURL();};
  document.getElementById("labels").onchange=e=>{
    labelMode=e.target.value; schedule(); saveURL();};
  document.getElementById("links").onchange=e=>{
    linkCount=+e.target.value; topPairs=null; schedule(); saveURL();};
  document.getElementById("q").oninput=e=>{
    query=e.target.value.toLowerCase().trim(); schedule();};

  document.getElementById("filters").innerHTML =
    ["sshomp","ph","etkad"].map(s=>
      '<label class="chk"><input type="checkbox" id="f_'+s+'" checked>'+SRCNAME[s]+'</label>').join("")+
    '<label class="chk"><input type="checkbox" id="f_steps">only workflows with steps</label>'+
    '<label class="chk"><input type="checkbox" id="f_tag">only human-declared methods</label>';
  ["sshomp","ph","etkad"].forEach(s=>document.getElementById("f_"+s).onchange=
    e=>{show[s]=e.target.checked; schedule();});
  document.getElementById("f_steps").onchange=e=>{show.stepsOnly=e.target.checked; schedule();};
  document.getElementById("f_tag").onchange=e=>{show.taggedOnly=e.target.checked; schedule();};

  document.getElementById("wReset").onclick=()=>setW(D.default_w);
  document.querySelectorAll("[data-preset]").forEach(b=>
    b.onclick=()=>{const o={}; o[b.dataset.preset]=1; setW(o);});

  document.getElementById("theme").onclick=()=>setTheme(theme==="dark"?"light":"dark");
  document.getElementById("typeup").onclick=cycleType;
  document.getElementById("help").onclick=()=>{
    document.getElementById("intro").style.display="flex";};
  document.getElementById("introGo").onclick=closeIntro;

  /* evaluation */
  const ev=D.eval, base=ev._popularity_baseline;
  const ranked=FAC.filter(f=>ev[f]!==undefined).sort((a,b)=>ev[b]-ev[a]);
  const top=Math.max(base, ...ranked.map(f=>ev[f]));
  document.getElementById("evalBox").innerHTML =
    '<p class="hint">A map can look convincing and know nothing. So here is a test '+
    'it could fail: hide a fifth of a workflow’s methods, find its '+ev._k+' nearest '+
    'neighbours using <em>one aspect on its own</em>, and see whether their methods '+
    'include the hidden ones.</p>'+
    '<p class="hint">If an aspect scores above <b>'+base.toFixed(0)+'%</b> it knows '+
    'something real. Below that, you would do better by ignoring it and guessing '+
    'the commonest methods every time.</p>'+
    ranked.map(f=>{
      const leak=(f==="method"||f==="goal");
      const cls=leak?"flat":(ev[f]>base+3?"good":ev[f]<base+1?"bad":"flat");
      return '<div class="evrow"><b>'+FNAME[f]+
        (leak?' <span style="color:var(--ink4)">*</span>':'')+
        '</b><span class="'+cls+'">'+ev[f].toFixed(0)+'%</span></div>'+
        '<div class="meter"><i style="width:'+(100*ev[f]/top).toFixed(1)+'%;background:'+
        (leak?"var(--ink4)":(ev[f]>base+3?"#5d8f6c":"#a8623a"))+'"></i></div>';}).join("")+
    '<div class="evrow" style="border-top:1px solid var(--line);padding-top:9px">'+
    '<span style="color:var(--ink3)">guessing the commonest</span>'+
    '<span style="color:var(--ink3)">'+base.toFixed(0)+'%</span></div>'+
    '<p class="aside" style="margin-top:14px">Two results worth knowing. '+
    '<b style="color:var(--ink2)">Order of steps</b> knows nothing about subject, '+
    'wording or software, and still beats both — projects that proceed the same way '+
    'do the same things. <b style="color:var(--ink2)">Software</b> falls below the '+
    'line: sharing tools is not evidence of doing similar work.</p>'+
    '<p class="aside">* Methods and Kind of work are versions of the answer being '+
    'tested, so their scores are a ceiling rather than a finding.</p>'+
    '<p class="aside"><a href="how_it_works.html" target="_blank" rel="noopener">'+
    'The full method, with a worked example &rarr;</a></p>';

  /* shape */
  const sh=D.shape.all, order=Object.keys(sh).sort((a,b)=>sh[a].mean-sh[b].mean);
  const tot=Object.values(sh).reduce((a,b)=>a+b.n,0);
  document.getElementById("shapeBox").innerHTML =
    '<p class="hint">Where in a project each kind of work typically falls. Left is '+
    'the first step, right is the last, from '+tot+' steps that come in a stated '+
    'order.</p>'+
    '<div style="position:relative">'+
    order.map(g=>'<div class="evrow"><b>'+g+'</b>'+
      '<span style="color:var(--ink3)">'+sh[g].n+' steps</span></div>'+
      '<div class="meter"><i style="left:'+(sh[g].mean*100-1).toFixed(0)+
      '%;width:5px;background:'+goalCol(g)+'"></i></div>').join("")+
    '</div><p class="aside">Discovery comes before capture: the work begins by '+
    'finding out what exists, not by collecting. Interpretation arrives early, '+
    'before analysis rather than after it. And the middle is a near-tie between '+
    'analysis, enrichment, creation and storage — which is what a loop looks like '+
    'when you average it, not a pipeline.</p>';

  /* transitions */
  const tr=D.transitions;
  document.getElementById("flowBox").innerHTML =
    '<p class="hint">How often one kind of work is followed by another, across the '+
    tr.from+' workflows that record their steps in order. An arrow marked '+
    '<span style="color:var(--accent)">&#8630;</span> runs backwards through the '+
    'usual sequence — that is a project looping, not a project going wrong.</p><table>'+
    tr.edges.slice(0,14).map(e=>{
      const back=D.goal_order.indexOf(e.b)<D.goal_order.indexOf(e.a);
      return '<tr><td'+(back?' style="color:var(--accent)"':'')+'>'+e.a+' &rarr; '+e.b+
        (back?' <span title="runs backwards">&#8630;</span>':'')+
        '</td><td class="n">'+e.n+'</td></tr>';}).join("")+'</table>';

  document.getElementById("stamp").textContent=D.stamp||"";
}

/* ================= detail panel ================= */
function renderDetail(i){
  const w=W[i], nb=neighbours(i,12);
  const badge=(w.method_src==="declared")?"declared by a person":"inferred from the prose";
  detail.innerHTML =
    '<div class="dhead"><button class="dclose" id="dclose" aria-label="Close">&times;</button>'+
    '<h2>'+esc(w.title)+'</h2><div class="meta">'+SRCNAME[w.src]+' &middot; '+w.lang+
    ' &middot; '+w.nsteps+' step'+(w.nsteps===1?"":"s")+
    (w.ntagged?' ('+w.ntagged+' tagged)':'')+
    (w.url?' &middot; <a href="'+esc(w.url)+'" target="_blank" rel="noopener">open source</a>':'')+
    '</div></div>'+
    (w.desc?'<div class="dsec"><p class="hint" style="margin:0">'+
      esc(w.desc.slice(0,300))+(w.desc.length>300?"…":"")+'</p></div>':'')+
    '<div class="dsec"><h3>Methods <em>'+badge+'</em></h3>'+
      (w.methods.length?w.methods.map(m=>'<span class="chip">'+esc(m)+'</span>').join("")
        :'<p class="hint" style="margin:0">none recorded</p>')+'</div>'+
    (w.tools.length?'<div class="dsec"><h3>Software named</h3>'+
      w.tools.map(t=>'<span class="chip tool">'+esc(t)+'</span>').join("")+'</div>':"")+
    (w.topics.length?'<div class="dsec"><h3>Topics</h3>'+
      w.topics.slice(0,16).map(t=>'<span class="chip topic">'+esc(t)+'</span>').join("")+'</div>':"")+
    (w.steps.length?'<div class="dsec"><h3>Steps <em>'+w.steps.length+'</em></h3>'+
      '<ol class="steps">'+w.steps.slice(0,30).map(s=>'<li><div class="st">'+
        esc(s.title||"(untitled)")+'</div>'+
        (s.methods.length?'<div class="sm">'+esc(s.methods.join(" · "))+'</div>':'')+
        '</li>').join("")+'</ol>'+
      (w.steps.length>30?'<p class="hint">+'+(w.steps.length-30)+' more</p>':'')+'</div>':"")+
    '<div class="dsec"><h3>Most similar <em>under your weights</em></h3>'+
    (nb.length?nb.map(p=>{
      const j=p[0], s=p[1], ws=why(i,j).slice(0,3);
      const shf=ws.length?sharedFeatures(i,j,ws[0][0]).slice(0,5):[];
      const off=!visible(j);
      return '<button class="nb" data-i="'+j+'"'+(off?' style="opacity:.5"':'')+'>'+
        '<div class="t">'+esc(W[j].title)+'</div>'+
        '<div class="r"><span class="pct">'+(s*100).toFixed(0)+'%</span>'+
        '<span class="sim"><i style="width:'+Math.min(100,s*100).toFixed(0)+'%"></i></span>'+
        '<span>'+SRCNAME[W[j].src]+(off?" · filtered out":"")+'</span></div>'+
        (ws.length?'<div class="sh">via <b>'+ws.map(x=>x[0]).join(", ")+'</b>'+
          (shf.length?' &middot; shares '+esc(shf.join(", ")):'')+'</div>':'')+
        '</button>';}).join("")
      :'<p class="hint" style="margin:0">Nothing is similar under the current '+
       'weights — try raising an aspect.</p>')+'</div>';
  document.getElementById("dclose").onclick=deselect;
  detail.querySelectorAll(".nb").forEach(b=>b.onclick=()=>select(+b.dataset.i,true));
}
function select(i,ease){
  const first=!detail.classList.contains("open");
  sel=i; detail.classList.add("open"); renderDetail(i);
  detail.scrollTop=0;
  if(first) requestAnimationFrame(()=>{ centreOn(i); });
  else if(ease) centreOn(i);
  schedule(); saveURL();
}
function deselect(){ sel=null; detail.classList.remove("open"); schedule(); saveURL(); }
/* Keep the selection inside the part of the canvas the panel does not cover. */
function centreOn(i){
  const availL=40, availR=vw-inset()-40;
  const x=sx(i), y=sy(i);
  let dx=0, dy=0;
  if(x>availR) dx=availR-x; else if(x<availL) dx=availL-x;
  if(y>vh-60) dy=vh-60-y; else if(y<60) dy=60-y;
  if(!dx&&!dy) return;
  const steps=14; let k=0;
  (function step(){ k++; ox+=dx/steps; oy+=dy/steps; draw();
    if(k<steps) requestAnimationFrame(step); })();
}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}

/* ================= reading preferences ================= */
function setTheme(t){
  theme=t; P=PALS[t];
  document.documentElement.setAttribute("data-theme",t);
  document.getElementById("theme").innerHTML = t==="dark" ? "&#9681;" : "&#9680;";
  document.getElementById("theme").title =
    t==="dark" ? "Switch to a light background" : "Switch to a dark background";
  try{localStorage.setItem("wfa_theme",t);}catch(e){}
  legend(); schedule();
}
const SIZES=["15px","16.5px","18px","13.5px"];
let sizeIx=0;
function cycleType(){
  sizeIx=(sizeIx+1)%SIZES.length;
  document.documentElement.style.setProperty("--base",SIZES[sizeIx]);
  try{localStorage.setItem("wfa_size",String(sizeIx));}catch(e){}
  requestAnimationFrame(()=>{resize(); draw();});
}
function closeIntro(){
  document.getElementById("intro").style.display="none";
  try{localStorage.setItem("wfa_seen","1");}catch(e){}
  cv.focus();
}

/* ================= interaction ================= */
function pick(mx,my){
  let best=null,bd=1e9;
  for(let i=0;i<N;i++){
    if(!visible(i) && i!==sel) continue;
    const d=Math.hypot(sx(i)-mx, sy(i)-my), lim=Math.max(9,radius(i)+5);
    if(d<lim && d<bd){bd=d;best=i;}
  }
  return best;
}
cv.addEventListener("pointerdown",e=>{
  dragging=true; moved=false; lx=e.clientX; ly=e.clientY;
  cv.classList.add("grabbing"); cv.setPointerCapture(e.pointerId);
});
cv.addEventListener("pointerup",e=>{
  dragging=false; cv.classList.remove("grabbing");
  try{cv.releasePointerCapture(e.pointerId);}catch(err){}
  if(moved) return;
  const r=cv.getBoundingClientRect();
  const i=pick(e.clientX-r.left,e.clientY-r.top);
  if(i!==null) select(i); else deselect();
});
cv.addEventListener("pointercancel",()=>{dragging=false; cv.classList.remove("grabbing");});
cv.addEventListener("pointermove",e=>{
  const r=cv.getBoundingClientRect(), mx=e.clientX-r.left, my=e.clientY-r.top;
  if(dragging){
    if(Math.abs(e.clientX-lx)+Math.abs(e.clientY-ly)>3) moved=true;
    ox+=e.clientX-lx; oy+=e.clientY-ly; lx=e.clientX; ly=e.clientY;
    clampPan();
    document.getElementById("tip").style.display="none"; hover=null;
    schedule(); return;
  }
  const i=pick(mx,my), tip=document.getElementById("tip");
  if(i!==hover){ hover=i; schedule(); }
  if(i===null){ tip.style.display="none"; return; }
  const w=W[i];
  tip.innerHTML='<div class="t">'+esc(w.title)+'</div><div class="m">'+
    SRCNAME[w.src]+' &middot; '+w.methods.length+' method'+(w.methods.length===1?"":"s")+
    ' &middot; '+w.nsteps+' step'+(w.nsteps===1?"":"s")+'</div>'+
    (sel!==null&&sel!==i?'<div class="s">'+(BS[sel*N+i]*100).toFixed(0)+
      '% similar to the selection</div>':'');
  tip.style.display="block";
  const tw=tip.offsetWidth, th=tip.offsetHeight;
  let tx=mx+16, ty=my+16;
  if(tx+tw>vw-inset()-10) tx=mx-tw-16;
  if(tx<8) tx=8;
  if(ty+th>vh-10) ty=my-th-16;
  tip.style.left=tx+"px"; tip.style.top=ty+"px";
});
cv.addEventListener("pointerleave",()=>{
  document.getElementById("tip").style.display="none";
  if(hover!==null){hover=null; schedule();}
});
cv.addEventListener("wheel",e=>{
  e.preventDefault();
  const r=cv.getBoundingClientRect(), mx=e.clientX-r.left, my=e.clientY-r.top;
  zoomAt(mx,my,Math.exp(-e.deltaY*(e.deltaMode===1?0.02:0.0012)));
},{passive:false});
function zoomAt(mx,my,k){
  const nk=Math.max(0.35*baseScale, Math.min(26*baseScale, scale*k))/scale;
  ox=mx-(mx-ox)*nk; oy=my-(my-oy)*nk; scale*=nk; clampPan(); schedule();
}
/* Panning without a leash lets you drag the whole corpus off the edge and stare
   at an empty rectangle. Keep a margin of the data box inside the viewport. */
function clampPan(){
  if(!XY) return;
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  for(let i=0;i<N;i++){
    const x=XY[i][0]*scale, y=XY[i][1]*scale;
    if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y;
  }
  /* Require half the smaller of (data box, viewport) to stay on screen. A fixed
     margin is not enough: it lets the whole corpus slide into a corner where the
     surviving sliver contains no nodes at all. */
  const right=vw-inset();
  const kx=0.5*Math.min(x1-x0, right), ky=0.5*Math.min(y1-y0, vh);
  ox=Math.min(right-kx-x0, Math.max(kx-x1, ox));
  oy=Math.min(vh-ky-y0,    Math.max(ky-y1, oy));
}
document.getElementById("zin").onclick=()=>zoomAt((vw-inset())/2,vh/2,1.35);
document.getElementById("zout").onclick=()=>zoomAt((vw-inset())/2,vh/2,1/1.35);
document.getElementById("zfit").onclick=()=>{fit(); schedule();};

window.addEventListener("keydown",e=>{
  const intro=document.getElementById("intro");
  if(e.key==="Escape" && intro.style.display!=="none"){ closeIntro(); return; }
  if(/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if(e.key==="Escape") deselect();
  else if(e.key==="?") intro.style.display="flex";
  else if(e.key==="f"||e.key==="F"){fit(); schedule();}
  else if(e.key==="+"||e.key==="="){zoomAt((vw-inset())/2,vh/2,1.35);}
  else if(e.key==="-"){zoomAt((vw-inset())/2,vh/2,1/1.35);}
  else if(e.key==="e"||e.key==="E"){
    const es=[]; for(let i=0;i<N;i++) if(W[i].src==="etkad") es.push(i);
    if(!es.length) return;
    const at=es.indexOf(sel); select(es[(at+1)%es.length],true);
  } else if(e.key==="/"){ e.preventDefault(); document.getElementById("q").focus(); }
});
window.addEventListener("blur",()=>{dragging=false; cv.classList.remove("grabbing");});

/* ================= export + url ================= */
document.getElementById("png").onclick=()=>{
  const a=document.createElement("a");
  a.download="workflow_galaxy_"+posMode+".png";
  a.href=cv.toDataURL("image/png"); a.click();};
document.getElementById("csv").onclick=()=>{
  const rows=[["workflow","source","neighbour","neighbour_source","similarity","via"]];
  for(let i=0;i<N;i++) for(const p of neighbours(i,5))
    rows.push([W[i].title,W[i].src,W[p[0]].title,W[p[0]].src,p[1].toFixed(4),
               why(i,p[0]).slice(0,2).map(x=>x[0]).join("|")]);
  const csv=rows.map(r=>r.map(c=>'"'+String(c).replace(/"/g,'""')+'"').join(",")).join(NL);
  const a=document.createElement("a"); a.download="workflow_neighbours.csv";
  a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})); a.click();};
document.getElementById("link").onclick=e=>{
  if(navigator.clipboard) navigator.clipboard.writeText(location.href);
  const b=e.target; const t=b.textContent; b.textContent="Copied";
  setTimeout(()=>b.textContent=t,1200);};

function saveURL(){
  const p=new URLSearchParams();
  p.set("w",FAC.map(f=>wgt[f]).join(","));
  p.set("p",posMode); p.set("c",colour);
  p.set("l",labelMode); p.set("k",String(linkCount));
  if(sel!==null) p.set("s",W[sel].id);
  history.replaceState(null,"","#"+p.toString());
}
function loadURL(){
  if(!location.hash) return;
  const p=new URLSearchParams(location.hash.slice(1));
  if(p.get("w")){const v=p.get("w").split(","); FAC.forEach((f,i)=>wgt[f]=+v[i]||0);}
  if(p.get("p")) posMode=p.get("p");
  if(p.get("c")) colour=p.get("c");
  if(p.get("l")) labelMode=p.get("l");
  if(p.get("k")!==null) linkCount=+p.get("k")||0;
  if(p.get("s")){const i=W.findIndex(w=>w.id===p.get("s")); if(i>=0) sel=i;}
}

function resize(){
  const r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
  vw=r.width; vh=r.height;
  cv.width=Math.round(vw*dpr); cv.height=Math.round(vh*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
}

/* ---- boot ---- */
let savedTheme=null, savedSize=null, seen=null;
try{ savedTheme=localStorage.getItem("wfa_theme");
     savedSize=localStorage.getItem("wfa_size");
     seen=localStorage.getItem("wfa_seen"); }catch(e){}
if(savedSize!==null){ sizeIx=+savedSize||0;
  document.documentElement.style.setProperty("--base",SIZES[sizeIx]); }
loadURL();
if(posMode==="custom") custom=customLayout(70);
BS=blended();
buildWeights(); buildRail();
setTheme(savedTheme || (window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
resize(); fit();
document.getElementById("colour").value=colour;
document.getElementById("posMode").value=posMode;
document.getElementById("labels").value=labelMode;
document.getElementById("links").value=String(linkCount);
if(sel!==null){ detail.classList.add("open"); renderDetail(sel); fit(); }
draw();
if(seen) document.getElementById("intro").style.display="none";
let rt=0;
window.addEventListener("resize",()=>{clearTimeout(rt);
  rt=setTimeout(()=>{resize(); fit(); draw();},120);});
</script>
"""


def main():
    p = os.path.join(WORK, "atlas.json")
    if not os.path.exists(p):
        sys.exit(f"missing {p} — run 3_layout.py first")
    data = json.load(open(p, encoding="utf-8"))
    n = len(data["workflows"])
    by = {}
    for w in data["workflows"]:
        by[w["src"]] = by.get(w["src"], 0) + 1
    data["stamp"] = (f"Built {datetime.date.today().isoformat()} · {n} workflows · "
                     + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
    html = TPL.replace("__DATA__", json.dumps(data, ensure_ascii=False,
                                              separators=(",", ":")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"-> {OUT}  ({os.path.getsize(OUT)/1e6:.2f} MB, {n} workflows)")


if __name__ == "__main__":
    main()
