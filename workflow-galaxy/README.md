# Workflow Galaxy — 237 workflows, compared on aspects you choose

The unit here is the **workflow**, not the method. The map answers one question —
*which workflows are like this one?* — and lets you say what you mean by "like".

```
    tool-galaxy       tool   --used-by-->  workflow      bioinformatics, 632 tool nodes
    method-galaxy     method --used-by-->  object        DH methods, 147 + 2,376 nodes
    workflow-galaxy   workflow itself is the node        237 workflows, 7 comparable aspects
```

## Why this exists and the method galaxy did not settle it

The method galaxy compared *methods*; workflows came along as an afterthought, and
there were only ten Estonian ones. Two things changed that:

1. **The Marketplace does have staged workflows — 108 of them, 729 ordered steps.**
   The v1 README said its `step` category was empty. That was wrong in an
   interesting way: steps are not indexed by `item-search`, so they never appear in
   the facet counts, but they come back inline under `composedOf` on the
   `/workflows` endpoint, in order, carrying their own TaDiRAH activity properties.
   48 of the 108 tag per step.
2. **Programming Historian** publishes 119 English lessons whose index page carries
   each lesson's activity verb, topic tags and difficulty, and whose bodies are
   ordered sections — a second corpus of things with steps.

With ETKAD's ten, that is 237 workflows: enough to compare workflows to each other
rather than only to a method vocabulary.

## Choosing what "similar" means

Seven aspects, each a bag of features, each with a slider:

| aspect | features | what it finds |
|---|---|---|
| **method** | TaDiRAH activities | workflows that do the same operations |
| **goal** | the 8 TaDiRAH goal groups | the same operations, coarsely |
| **tool** | named software, matched against 2,841 Marketplace tool names | the same software stack |
| **topic** | keywords, disciplines, EMS subjects | the same subject matter |
| **material** | input/output formats, media types | the same kind of stuff worked on |
| **flow** | ordered goal bigrams + position bins | the same *shape*, whatever the subject |
| **text** | TF-IDF terms of title, abstract and step titles | the same wording |

The vectors ship to the browser and cosine similarity is recomputed there on every
slider move, so the ranking, the neighbour links and the "custom blend" layout all
follow your weights rather than a prebaked choice.

**The map draws its own similarity network**, the closest 120 pairs under the
current weights, and that is what a slider visibly changes. Without it the sliders
felt broken: they were working, but with a precomputed layout the dots do not move,
and with nothing selected there was no feedback except a line of small text. The
network is also the quickest way to see the tool result for yourself — set `tool` to
1 and everything else to 0, and the links fly across the whole map at random,
because sharing software says almost nothing about doing the same work. Each neighbour is annotated with
*which* aspects produced the match and which features were shared, so a suggestion
can be checked rather than trusted.

Positions come from a precomputed UMAP per aspect; **custom blend** re-lays the map
out in the browser by stress majorisation on your exact weighting, and once you are
in that mode it follows the sliders live, warm-started from where the dots already
are so a drag nudges the map instead of throwing it into a new arrangement.

The ten ETKAD workflows are labelled by default so they can be found in a field of
237 — that is what the `labels` control is for, and turning it to *selection and
neighbours only* removes the special treatment. Source is encoded by shape as well
as colour, so they stay identifiable without it.

## Does the map know anything?

The honest question the earlier maps could not answer. Hide a fifth of each
workflow's methods, rank neighbours using **one aspect alone**, pool the methods of
the top 5, and see how many of the hidden ones come back.

```
method       79.2%   *derived from the target — a ceiling, not a result
goal         55.8%   *same
flow         49.4%   shape alone, no content
text         48.1%
topic        44.2%
material     40.3%
popularity   33.8%   baseline: always answer with the 12 commonest methods
tool         31.2%   below the baseline
```

Two findings sit in that table.

**Shape carries real information.** `flow` knows nothing about subject, wording or
software — only which kind of operation follows which — and it still predicts a
workflow's methods better than its topic or its prose. Workflows that proceed the
same way do the same things.

**Tool similarity carries none — it is actively worse than guessing.** Ranking
neighbours by shared software predicts a workflow's methods *below* the popularity
baseline. Python, OpenRefine and Voyant are used for everything, so "we use the same
tools" is not evidence of doing the same work; it is mild evidence of being in the
same tooling fashion. That is a caution for any registry tempted to recommend by
tool. (This number moved from 33.8% to 31.2% once the tool matcher was tightened —
the earlier figure was propped up by false positives.)

## The shape of a workflow, on 53 workflows instead of 9

Mean normalised position of each goal, 0 = first step, 1 = last:

```
Discovery ....... 0.24   (21 taggings)
Capture ......... 0.37   (46)
Interpretation .. 0.42   (38)
Analysis ........ 0.54   (90)
Enrichment ...... 0.54   (47)
Creation ........ 0.56   (25)
Storage ......... 0.56   (36)
Dissemination ... 0.75   (22)
```

The v1 arc — built from nine Estonian workflows — put Capture first. With 53
workflows from three sources, **Discovery comes before Capture**: the work starts by
finding out what exists, not by collecting it. Interpretation arriving early (0.42),
before analysis rather than after, is the other correction, and it is the one that
argues hardest against reading these as pipelines. The middle of a run is a flat
tie between analysis, enrichment, creation and storage — evidence that this is a
loop, not a sequence.

## Measured results

```
Marketplace /workflows       108 workflows, 729 ordered steps, 48 tagged per step
Programming Historian        119 lessons, 1,657 ordered sections (front matter cut)
ETKAD                         10 workflows, 55 stages
Marketplace full corpus    6,305 items -> gazetteer of 2,841 tool names
total                        237 workflows
  with methods               183   with tools 206   with topics 230   with shape 44
map                        1.1 MB of self-contained HTML, 8 layouts
```

## Run

```bash
pip install scikit-learn umap-learn hdbscan numpy scipy   # hdbscan optional
cd workflow-galaxy
python 1_harvest.py       # ~2 min, all HTTP into memory
python 2_extract.py
python 3_layout.py
python 4_build_map.py     # -> workflow_galaxy.html
python 5_explain.py       # -> how_it_works.html
```

## How similarity is calculated

**[how_it_works.html](how_it_works.html)** is the technical sheet, linked from the
map itself. Short version: each workflow becomes seven bags of feature strings;
features are weighted by inverse document frequency; two workflows are compared by
cosine similarity on those weighted vectors, once per aspect; the seven results are
combined as a weighted mean. Cosine rather than Euclidean because it is indifferent
to how *much* a record declares — otherwise ETKAD's 8–20 methods per workflow would
separate from the Marketplace's 1–3 on verbosity alone.

Every figure on that page — the idf table, the worked example, the per-aspect
cosines — is computed by `5_explain.py` from `work/atlas.json` rather than written
by hand, so it cannot drift out of step with the data.

Writing it turned up a correction worth keeping: I had assumed a few methods would
dominate and idf would be doing heavy lifting. It isn't. **The commonest method in
the corpus, `Machine Learning`, is on 31 of 237 workflows (13%)**, and only 8
methods reach 15. The method vocabulary is spread thin, so idf has far less
leverage here than in `Subject` or `Wording`, where the distributions are steep.

Nothing is cloned. 7 MB of JSON on disk.

## Keys

`click` select · `Esc` deselect · `f` fit · `+` / `-` zoom · `/` search ·
`?` the introduction · `e` cycle the ETKAD workflows · drag to pan · wheel to zoom

## Interface notes

Built to the usual guidance for graph and scatter UIs: progressive disclosure
rather than showing everything at once, a colourblind-safe palette (Okabe-Ito),
**shape as well as colour** for source so the encoding survives greyscale and every
kind of colour vision, and a single clear z-order so nothing hides data silently.

**Written for a humanities reader, not for whoever built it.** The aspects are
named in the interface as *Methods, Kind of work, Software, Subject, Materials,
Order of steps, Wording* — `flow` and `material` meant nothing to anyone who had
not read the source. Slider values read *ignore / a little / somewhat / a lot /
above all*, because a weight of 0.7 is false precision for a judgement of this
kind. A **What am I looking at?** panel opens on first visit and stays available
from the `?` button; it says in three paragraphs what a dot is, what the map does
and does not know, and why the left-hand panel is the important part. The analysis
sections state their findings in prose rather than leaving a reader to interpret a
column of percentages.

**Both themes, and a type-size control.** Dark is built on `#15151a` rather than
pure black, which causes halation — the glow that makes small light-on-dark type
swim; light is a warm paper white. The theme follows the operating system on first
visit and is remembered thereafter. Okabe-Ito was designed against white, so the
dark theme uses it as published and the light theme darkens it to hold contrast
against paper. No `color-mix()` or `backdrop-filter`: the file has to open on
whatever browser is to hand.

Four rendering bugs were found by screenshotting the thing at different zoom levels
rather than by reading the code, and are worth recording because they are easy to
reintroduce:

- **Labels were ranked before being clipped.** The old loop scored all 237 nodes,
  took the best 70, and *then* discarded the off-screen ones — so zooming in spent
  the entire label budget on nodes nobody could see. Candidates are now restricted
  to the viewport first.
- **The collision test compared a centre-line y against a top-edge y**, so labels
  overlapped. It is a plain rectangle intersection now, seeded with the bounding
  boxes of the legend, readout and zoom control so labels never land underneath
  them. Labels that would run off the right edge flip to the left of their node.
- **Node radius ignored zoom**, which turned a zoomed-in map into a few specks in
  an empty field. Radius now grows sub-linearly with zoom, and labels fade in by
  degrees instead of all appearing past a hard threshold.
- **Panning had no leash.** You could drag the whole corpus off the edge and be
  left staring at an empty rectangle with no way back but the fit button. Half of
  the smaller of (data box, viewport) now always stays on screen.

Two smaller inconsistencies went with them: the custom layout was seeded from a
layout that did not exist yet, so every run started from a different random spiral;
and a selection hidden by a filter still drew its neighbour links, converging on
nothing.

## Honest limitations

- **Declared and inferred methods are not the same evidence.** Marketplace and
  ETKAD methods were applied by a human; Programming Historian's are matched out of
  the prose. Every workflow records which it is, the map can filter to declared
  only, and colour-by-`msrc` shows the split — but a match between an inferred tag
  and a declared one is weaker than between two declared ones, and half the corpus
  is inferred.
- **`Python` was dropped as a tool.** The ubiquity filter removes any name that
  fires in more than 35% of the corpus, which in a corpus of programming tutorials
  catches Python and GitHub. They are genuinely used; they just cannot discriminate.
- **Tool matching is deliberately conservative.** The Marketplace contains real
  tools named *Topic*, *Things*, *Origin*, *Icon*, *Pattern* and *Concordance*, and
  every one of them fired on ordinary prose. Matching is now case-sensitive against
  the tool's own capitalisation — with an exemption for names that could not be
  mistaken for a word (a digit, an internal capital, punctuation), so `Word2Vec`
  still finds `word2vec`. This trades recall for precision: some genuine mentions
  are certainly missed.
- **`material` is nearly empty** — 19 of 237 workflows declare input or output
  formats. The slider works, but it is a facet waiting for data, and it is the one
  most worth pushing on: "what does this workflow take in and give out" is the
  question a registry actually needs, and almost nobody records it.
- **The shape rests on 53 workflows**, of which 10 are ETKAD's. It is a real
  measurement of a small sample, not a fact about digital humanities.
- **Similar-by-topic is partly similar-by-language.** ETKAD's topics are Estonian
  strings and match only each other, so the ten cluster together under any topic
  weighting for a reason that is not intellectual. Weight `method` or `flow` when
  you want a genuinely cross-lingual comparison.
- **The translation is still mine.** `vocab.py` carries the same hand-built
  Estonian→English TaDiRAH bridge as the method galaxy and deserves review by
  someone who owns the Estonian vocabulary.

## Worth doing next

- **Populate `material`.** Input/output format is declared by 19 workflows and it is
  the aspect that would turn the atlas into a real next-step recommender: given
  what you are holding, what can be done to it.
- **Contribute ETKAD's ten to the Marketplace** as workflows with steps. The model
  fits exactly, and it would put Estonian work into the corpus everyone else
  queries rather than only into our own map.
- **Join the tool layer.** `tool-galaxy` has 632 tool nodes with co-usage
  structure; the `tool` facet here has 295 names. The two are the same kind of
  object and could share an axis.
