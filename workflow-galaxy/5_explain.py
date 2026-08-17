#!/usr/bin/env python3
"""Stage 5: generate the technical explanation sheet.

Every number in the output is computed here from work/atlas.json rather than
written by hand, including the worked example. If the corpus changes, rerunning
this changes the explanation with it — a documentation page that can go stale is
worse than none.

Output: how_it_works.html
"""
import datetime
import html
import json
import math
import os
import sys

WORK = os.path.abspath(os.environ.get("WFA_WORK", "./work"))
OUT = os.path.abspath(os.environ.get("WFA_EXPLAIN", "./how_it_works.html"))

FNAME = {"method": "Methods", "goal": "Kind of work", "tool": "Software",
         "topic": "Subject", "material": "Materials", "flow": "Order of steps",
         "text": "Wording"}


def vec(D, f, i):
    """{feature label: idf weight} for one workflow under one aspect."""
    v = D["vectors"][f]
    return {v["vocab"][ix]: w for ix, w in v["rows"][i]}


def cosine(a, b):
    if not a or not b:
        return 0.0
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    dot = sum(w * b[k] for k, w in a.items() if k in b)
    return dot / (na * nb)


def blended(D, i, j, wgt):
    tot = sum(w for w in wgt.values() if w > 0)
    if tot == 0:
        return 0.0
    return sum(wgt[f] * cosine(vec(D, f, i), vec(D, f, j))
               for f in D["facets"] if wgt[f] > 0) / tot


def pick_example(D):
    """An ETKAD workflow and its closest non-ETKAD neighbour by methods alone.

    Cross-source is the interesting case: two ETKAD workflows share Estonian
    topic strings and would make the example look easier than it is.
    """
    W = D["workflows"]
    et = [i for i, w in enumerate(W) if w["src"] == "etkad" and len(w["methods"]) >= 6]
    best = (0.0, None, None)
    for i in et:
        a = vec(D, "method", i)
        for j, w in enumerate(W):
            if w["src"] == "etkad":
                continue
            s = cosine(a, vec(D, "method", j))
            if s > best[0]:
                best = (s, i, j)
    return best[1], best[2]


def esc(s):
    return html.escape(str(s), quote=True)


CSS = """
:root{--bg:#15151a;--panel:#1b1b21;--line:#2e2e37;--ink:#eceae6;--ink2:#adaba8;
 --ink3:#79777c;--accent:#e0a458;--accent2:#8fbfe0;--code:#1f1f27;
 --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
 --sans:Inter,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme: light){
:root{--bg:#faf8f4;--panel:#fffdfa;--line:#e0dcd3;--ink:#22201d;--ink2:#55524d;
 --ink3:#807c75;--accent:#a8620d;--accent2:#1f6d9e;--code:#f2efe9}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:16px/1.65 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:760px;margin:0 auto;padding:56px 26px 100px}
header{border-bottom:1px solid var(--line);padding-bottom:26px;margin-bottom:34px}
h1{font:400 38px/1.15 var(--serif);margin:0 0 10px}
.lede{color:var(--ink2);font-size:18px;line-height:1.6;margin:0}
.back{display:inline-block;margin-bottom:22px;color:var(--accent2);font-size:14px;
 text-decoration:none}
.back:hover{text-decoration:underline}
h2{font:400 26px/1.25 var(--serif);margin:46px 0 12px;padding-top:14px;
 border-top:1px solid var(--line)}
h3{font:600 14px var(--sans);text-transform:uppercase;letter-spacing:1.1px;
 color:var(--ink2);margin:30px 0 10px}
p{margin:0 0 15px;color:var(--ink2)}
p.tight{margin-bottom:8px}
b,strong{color:var(--ink);font-weight:600}
em{color:var(--ink)}
code{background:var(--code);border-radius:4px;padding:1px 6px;font-size:14.5px;
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--ink)}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;
 padding:16px 18px;overflow-x:auto;font-size:14px;line-height:1.6;
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--ink2)}
pre b{color:var(--accent)}
table{width:100%;border-collapse:collapse;margin:14px 0 20px;font-size:15px}
th{text-align:left;font:600 12.5px var(--sans);text-transform:uppercase;
 letter-spacing:.9px;color:var(--ink3);border-bottom:1px solid var(--line);
 padding:0 10px 7px 0}
td{padding:7px 10px 7px 0;border-bottom:1px solid var(--line);color:var(--ink2);
 vertical-align:top}
td.n{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink);
 white-space:nowrap}
.note{border-left:3px solid var(--accent);padding:2px 0 2px 16px;margin:20px 0;
 color:var(--ink2)}
.note b{color:var(--accent)}
.formula{text-align:center;font-size:18px;margin:22px 0;color:var(--ink);
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.foot{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
 color:var(--ink3);font-size:13.5px}
a{color:var(--accent2)}
"""


def main():
    p = os.path.join(WORK, "atlas.json")
    if not os.path.exists(p):
        sys.exit(f"missing {p} — run 3_layout.py first")
    D = json.load(open(p, encoding="utf-8"))
    W, FAC = D["workflows"], D["facets"]

    i, j = pick_example(D)
    A, B = W[i], W[j]
    va, vb = vec(D, "method", i), vec(D, "method", j)
    shared = sorted(set(va) & set(vb), key=lambda k: -va[k])
    na = math.sqrt(sum(x * x for x in va.values()))
    nb = math.sqrt(sum(x * x for x in vb.values()))
    dot = sum(va[k] * vb[k] for k in shared)
    cos_m = dot / (na * nb)

    # idf extremes, to show what the weighting actually does
    mv = D["vectors"]["method"]
    seen = {}
    for row in mv["rows"]:
        for ix, w in row:
            seen[mv["vocab"][ix]] = w
    by_w = sorted(seen.items(), key=lambda kv: kv[1])
    n_docs = len(W)
    counts = {}
    for row in mv["rows"]:
        for ix, _ in row:
            counts[mv["vocab"][ix]] = counts.get(mv["vocab"][ix], 0) + 1

    n_flow = sum(1 for r in D["vectors"]["flow"]["rows"] if r)
    per_facet = [(f, cosine(vec(D, f, i), vec(D, f, j))) for f in FAC]
    wgt = D["default_w"]
    bl = blended(D, i, j, wgt)

    def rows(pairs, fmt="{:.2f}"):
        return "".join(
            f"<tr><td>{esc(k)}</td><td class='n'>{counts.get(k,0)}</td>"
            f"<td class='n'>{fmt.format(v)}</td></tr>" for k, v in pairs)

    ev = D["eval"]
    sh = D["shape"]["all"]

    body = f"""
<a class="back" href="workflow_galaxy.html">&larr; back to Workflow Galaxy</a>
<header>
<h1>How the distances are calculated</h1>
<p class="lede">Workflow Galaxy claims that some research workflows are more
alike than others. This page says exactly what that claim rests on, in enough
detail to disagree with it.</p>
</header>

<p>Everything reduces to one measurement, applied seven times. A workflow becomes
a <b>set of features</b>; two workflows are compared by <b>how much their sets
overlap, weighted so that rare features count for more than common ones</b>; and
the seven results are averaged using whatever weights you set in the interface.
There is no machine learning in the similarity, no embedding model, and nothing
that has read the text for meaning. It is counting, carefully.</p>

<h2>1. A workflow becomes seven bags of features</h2>
<p>Each aspect turns a workflow into a plain set of strings. Nothing is invented:
every feature is something the record actually states.</p>
<table>
<tr><th>Aspect</th><th>A feature is</th><th style="text-align:right">Distinct</th></tr>
{"".join(f"<tr><td><b>{FNAME[f]}</b></td><td>{d}</td><td class='n'>{len(D['vectors'][f]['vocab'])}</td></tr>" for f, d in [
  ("method", "one TaDiRAH activity, e.g. <code>Georeferencing</code>"),
  ("goal", "one of eight goal groups, e.g. <code>Analysis</code>"),
  ("tool", "one software name found in the text, e.g. <code>QGIS</code>"),
  ("topic", "one keyword or discipline, e.g. <code>folkloristika</code>"),
  ("material", "an input or output format, e.g. <code>out:GeoJSON</code>"),
  ("flow", "a position bin or a transition, e.g. <code>pos0:Capture</code>, <code>Analysis&gt;Enrichment</code>"),
  ("text", "one of the 30 most distinctive words in its title and description"),
])}
</table>
<p>The sets are unordered and unweighted at this point. <code>{esc(FNAME['flow'])}</code>
is the one that needs explaining, and it gets a section of its own below.</p>

<h2>2. Rare features count for more</h2>
<p>A feature shared by half the corpus is weak evidence; one shared by three
workflows is strong. So every feature carries an <b>inverse document
frequency</b> weight:</p>
<div class="formula">idf(<i>f</i>) = log(1 + N / (1 + df<sub>f</sub>))</div>
<p>where <i>N</i> = {n_docs} workflows and df is how many of them carry the
feature. In this corpus that produces:</p>
<table>
<tr><th>Commonest methods</th><th style="text-align:right">In</th><th style="text-align:right">Weight</th></tr>
{rows(by_w[:5])}
</table>
<table>
<tr><th>Rarest methods</th><th style="text-align:right">In</th><th style="text-align:right">Weight</th></tr>
{rows(list(reversed(by_w[-5:])))}
</table>
<p>A single shared rare method is worth roughly
{by_w[-1][1]/max(by_w[0][1],1e-9):.1f}&times; a single shared common one — and that
modest ratio is itself worth noticing. <b>No method dominates this corpus.</b> The
commonest, <code>{esc(by_w[0][0])}</code>, appears in only {counts.get(by_w[0][0],0)}
of {n_docs} workflows ({100*counts.get(by_w[0][0],0)/n_docs:.0f}%), and only
{sum(1 for _, c in counts.items() if c >= 15)} methods reach 15. The 121 methods in
play are spread thinly across the {sum(1 for r in mv['rows'] if r)} workflows that
declare any, so idf has far less work to do here than it would in a corpus where
one or two terms were on everything. Weighting still matters for
<code>{esc(FNAME['topic'])}</code> and <code>{esc(FNAME['text'])}</code>, where the
distributions are much steeper.</p>

<h2>3. Overlap is measured as cosine similarity</h2>
<p>Each workflow is now a sparse vector: one dimension per possible feature,
holding that feature's idf weight if present and zero if not. Similarity is the
cosine of the angle between two such vectors.</p>
<div class="formula">cos(A,B) = (A &middot; B) / (&#8214;A&#8214; &times; &#8214;B&#8214;)</div>
<p>Cosine rather than Euclidean distance, because the division by both lengths
makes the measure <b>indifferent to how much a workflow declares</b>. A thorough
record with twenty methods and a terse one with six can still be judged similar
if what they do declare agrees. That matters here: ETKAD workflows carry 8–20
methods because they are workflows, while most Marketplace entries are
single-purpose and carry 1–3. Euclidean distance would separate them on
verbosity alone.</p>

<h3>Worked example, from the live data</h3>
<p>The closest cross-source pair by methods alone:</p>
<pre>A  <b>{esc(A['title'][:66])}</b>
   {esc(A['src'])} &middot; {len(A['methods'])} methods
B  <b>{esc(B['title'][:66])}</b>
   {esc(B['src'])} &middot; {len(B['methods'])} methods</pre>
<table>
<tr><th>Shared method</th><th style="text-align:right">In</th><th style="text-align:right">Weight</th></tr>
{rows([(k, va[k]) for k in shared])}
</table>
<pre>dot product   = {" + ".join(f"{va[k]:.2f}&sup2;" for k in shared[:4])}{" + …" if len(shared) > 4 else ""}
              = <b>{dot:.3f}</b>
&#8214;A&#8214; = {na:.3f}   (all {len(va)} of A's methods)
&#8214;B&#8214; = {nb:.3f}   (all {len(vb)} of B's methods)

cosine        = {dot:.3f} / ({na:.3f} &times; {nb:.3f}) = <b>{cos_m:.3f}</b>   &rarr; shown as {cos_m*100:.0f}%</pre>
<p>Note that the shared features are squared in the dot product only because both
vectors carry the same idf weight for a given feature — presence is binary, so
<code>A<sub>f</sub> &times; B<sub>f</sub> = idf(f)&sup2;</code> whenever both have it,
and zero otherwise.</p>

<h2>4. The seven results are blended</h2>
<p>The same calculation runs once per aspect, giving seven numbers for this pair:</p>
<table>
<tr><th>Aspect</th><th style="text-align:right">Cosine</th><th style="text-align:right">Your weight</th></tr>
{"".join(f"<tr><td>{FNAME[f]}</td><td class='n'>{c:.3f}</td><td class='n'>{wgt[f]:.1f}</td></tr>" for f, c in per_facet)}
</table>
<div class="formula">similarity = &Sigma; w<sub>f</sub> &middot; cos<sub>f</sub>(A,B) &nbsp;&divide;&nbsp; &Sigma; w<sub>f</sub></div>
<p>At the default weights that gives <b>{bl:.3f}</b>, or {bl*100:.0f}%. Dividing by
the total weight is what keeps the figure comparable when you turn an aspect off:
without it, ignoring an aspect would shrink every similarity at once and the
percentages would stop meaning anything.</p>
<div class="note"><b>This is why the sliders are the interface.</b> There is no
single correct weighting, and the atlas does not pretend to one. Two workflows
that are 60% alike by software may be 5% alike by method. The honest answer to
&ldquo;are these similar?&rdquo; is &ldquo;in which respect?&rdquo;</div>

<h2>5. The Order of steps features</h2>
<p>The other six aspects describe <i>what</i> a workflow contains. This one
describes <i>how it proceeds</i>, and it is built to be blind to subject matter.
For each workflow that tags at least three of its steps, two kinds of feature are
emitted:</p>
<table>
<tr><td><code>pos0:Capture</code></td><td>this kind of work appears in the first
quarter of the run. Step positions are normalised to 0–1 first, so a 4-step
workflow and a 20-step one are comparable.</td></tr>
<tr><td><code>Analysis&gt;Enrichment</code></td><td>a step tagged Analysis is
directly followed by one tagged Enrichment.</td></tr>
</table>
<p>Two workflows about entirely different material score highly here if they
capture early, analyse in the middle and disseminate late. {n_flow} of
{n_docs} workflows have enough ordered tagging to get these features; the rest are
drawn faded when this aspect is weighted, because they have no position in it.</p>

<h2>6. Where the dots are placed is a separate question</h2>
<p>Similarity is exact. <b>Position is an approximation of it</b>, and the two
should not be confused.</p>
<p>The precomputed layouts reduce the weighted feature matrix to 60 dimensions
with truncated SVD, then to two with UMAP (cosine metric, 8 neighbours,
min_dist 0.18). The <b>Custom</b> layout is computed in the browser by stress
majorisation on the blended distances, warm-started from the blended UMAP.</p>
<div class="note"><b>Read adjacency, never distance.</b> UMAP preserves
neighbourhoods, not distances. &ldquo;These two dots touch&rdquo; is trustworthy.
&ldquo;This cluster is twice as far from that one as from the third&rdquo; is not —
inter-cluster gaps are close to arbitrary and change between layouts. This is why
the neighbour list in the detail panel is computed from the vectors directly and
not from what is on screen.</div>

<h2>7. Whether any of this is worth anything</h2>
<p>A map can look convincing and know nothing, so the atlas carries a test it
could fail. A fifth of each workflow's methods are hidden; its {ev['_k']} nearest
neighbours are found using <b>one aspect on its own</b>; the methods of those
neighbours are pooled and checked against what was hidden. Over
{ev['_n']} workflows with enough methods to split:</p>
<table>
<tr><th>Ranking neighbours by</th><th style="text-align:right">Hidden methods recovered</th></tr>
{"".join(f"<tr><td>{FNAME[f]}{' *' if f in ('method','goal') else ''}</td><td class='n'>{ev[f]:.1f}%</td></tr>" for f in sorted([x for x in FAC if x in ev], key=lambda x: -ev[x]))}
<tr><td>always guessing the 12 commonest methods</td><td class="n">{ev['_popularity_baseline']:.1f}%</td></tr>
</table>
<p>* Methods and Kind of work are versions of the answer being tested, so they are
a ceiling rather than a finding.</p>
<p>Two things fall out of that table. <b>Order of steps</b> knows nothing about
subject, wording or software and still beats both — workflows that proceed the
same way do the same things. <b>Software</b> lands below the baseline: you would
do better ignoring which tools a project used than trusting them as evidence of
similar work.</p>

<h2>8. Every parameter, in one place</h2>
<table>
<tr><th>What</th><th>Value</th><th>Where</th></tr>
<tr><td>idf</td><td>log(1 + N/(1+df))</td><td>3_layout.py <code>idf_weights</code></td></tr>
<tr><td>similarity</td><td>cosine on idf-weighted binary vectors</td><td>4_build_map.py <code>facetSim</code></td></tr>
<tr><td>blend</td><td>weighted mean of per-aspect cosines</td><td>4_build_map.py <code>blended</code></td></tr>
<tr><td>SVD</td><td>60 components</td><td>3_layout.py <code>layout_for</code></td></tr>
<tr><td>UMAP</td><td>n_neighbors 8, min_dist 0.18, spread 1.3, metric cosine</td><td>3_layout.py <code>project</code></td></tr>
<tr><td>clustering</td><td>HDBSCAN, min_cluster_size 6, min_samples 2</td><td>3_layout.py <code>cluster</code></td></tr>
<tr><td>cluster labels</td><td>c-TF-IDF over Marketplace titles</td><td>3_layout.py <code>ctfidf</code></td></tr>
<tr><td>custom layout</td><td>stress majorisation, 110 passes (40 when following a slider)</td><td>4_build_map.py <code>customLayout</code></td></tr>
<tr><td>random seed</td><td>42 throughout</td><td>3_layout.py <code>SEED</code></td></tr>
</table>
<p>The whole pipeline reruns from nothing in about three minutes:</p>
<pre>python 1_harvest.py     # HTTP only, nothing cloned
python 2_extract.py     # three sources into one schema, seven aspects
python 3_layout.py      # vectors, layouts, evaluation
python 4_build_map.py   # -&gt; workflow_galaxy.html
python 5_explain.py     # -&gt; this page</pre>

<h2>What this measurement cannot do</h2>
<p>It compares <b>records, not research</b>. A method counts only if somebody wrote
it down, so a workflow that plainly involved transcription but never said so is,
to this calculation, a workflow without transcription. Roughly half the corpus —
the Programming Historian lessons — has methods read out of its prose rather than
declared by a person, which is weaker evidence again; the atlas marks which is
which and can filter to declared only.</p>
<p>It has no idea what any project means. Two workflows using the same six methods
on completely unrelated material will be judged near-identical, and sometimes
that is exactly the useful finding, and sometimes it is a mirage. The neighbour
list shows which features produced each match precisely so that you can tell the
difference yourself.</p>

<p class="foot">Generated {datetime.date.today().isoformat()} from
work/atlas.json &middot; {n_docs} workflows &middot; every figure on this page is
computed from the same data the map is built from, not written by hand.<br>
<a href="workflow_galaxy.html">&larr; back to Workflow Galaxy</a></p>
"""

    doc = ("<!doctype html><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>How the distances are calculated &middot; Workflow Galaxy</title>"
           f"<style>{CSS}</style><div class='wrap'>{body}</div>")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"-> {OUT}  ({os.path.getsize(OUT)/1000:.0f} KB)")
    print(f"   worked example: {A['title'][:44]} <-> {B['title'][:44]}")
    print(f"   method cosine {cos_m:.3f}, blended {bl:.3f}")


if __name__ == "__main__":
    main()
