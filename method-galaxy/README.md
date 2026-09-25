# DH Method Galaxy — ETKAD workflows inside European digital humanities

An interactive map of **digital-humanities research methods**, built from the SSH Open
Marketplace, with ETKAD's own workflows plotted into it.

The premise is the one the workflow-galaxy prototype could not satisfy: you cannot build a
map out of thirteen workflows, but you can **embed thirteen workflows into somebody else's
map**. The join is TaDiRAH — the same method vocabulary ETKAD already uses on its workflow
pages (in Estonian) and the Marketplace uses on 2,366 objects (in English). The tags are read
from the Estonian page of each workflow; titles, stage names, subjects and the prose searched
for tool names come from its English version.

```
    workflow-galaxy:  tool   used-by  workflow      -> bioinformatics, 632 nodes
    method-galaxy:    method used-by  object        -> humanities,   147 + 2,379 nodes
```

## What it shows

**Two spaces**, switchable, each laid out three different ways:

| Space | Nodes | Meaning of proximity |
|---|---|---|
| **Methods** | 147 TaDiRAH activities | the same objects use them |
| **Objects** | 2,379 tools, datasets, tutorials, publications, workflows | they share methods |

**Six things you can do with it:**

1. **Method paths.** ETKAD workflows are tagged with TaDiRAH terms *per stage*, so a workflow
   is a route through method space, not a bag of tags. Selecting one draws its numbered path.
2. **Gap report.** Which methods European DH uses and Estonian workflows do not.
3. **Adjacent opportunities.** Better than the gap report: unused methods ranked by how
   tightly European practice binds them to methods ETKAD *already* uses. "You do content
   analysis and NER; everyone who does those also does POS-tagging" beats "X is popular".
4. **Closest European objects.** For each ETKAD workflow, the Marketplace tools and tutorials
   with the most method overlap — a working "more like this" for the Registry.
5. **Tools named in the text.** Marketplace tool names matched literally against the Estonian
   prose. A direct statement of use, not an inferred similarity.
6. **Shape of a workflow.** Where in a workflow each kind of method happens — see below.

Plus: three distance metrics, colour by cluster / TaDiRAH goal / Estonian uptake / gap,
filters by goal, object type, source and language, a density field, search, PNG export,
CSV export of the gap analysis, and shareable `#`-URLs that restore the exact view.

## The shape of a humanities workflow

Only ETKAD tags methods **per stage, in order** — the Marketplace does not — so this is the
one question the Estonian data can answer and the European data cannot. Normalising each
workflow's stages to 0..1 and averaging across all 13 workflows, each of which breaks itself
into ordered stages, gives:

```
Discovery ..... 0.22   (22 taggings)   earliest
Enrichment .... 0.31   (28)
Capture ....... 0.32   (10)
Storage ....... 0.42   (17)
Analysis ...... 0.53   (71)  — by far the most tagged
Interpretation  0.59   (23)
Creation ...... 0.70   (28)
Dissemination . 0.82   (18)  latest
```

That arc — discover, enrich and capture, analyse, interpret, create, disseminate — is close
to TaDiRAH's own conceptual ordering, **recovered empirically from thirteen Estonian workflows
that were never asked to follow it**. With nine workflows Capture came first (on 3 taggings);
with thirteen, Discovery does — the work starts by finding out what exists, which is also
what workflow-galaxy finds across 57 workflows from three sources. The most common
transitions are Enrichment→Analysis (13), Analysis→Creation (13), Analysis→Interpretation (8)
and Discovery→Analysis (8), with Analysis→Enrichment (7) running backwards — the useful
detail: these workflows iterate between enriching and analysing rather than proceeding down
a pipeline.

## Measured results

```
SSH Open Marketplace harvested   6,305 items   (64 API calls; properties come back inline)
  ... carrying a TaDiRAH activity 2,366  (38%)
      tools & services 1,892 · training 223 · datasets 105 · publications 73 · workflows 73
ETKAD workflows                     13   (all 13 parsed, 8-22 methods each, 4-11 stages)
Estonian TaDiRAH terms              81 distinct -> 77 mapped to TaDiRAH2, 4 unmapped
distinct methods in play           147
methods used by ETKAD               73   (50%)
map                              147 methods + 2,379 objects, 6 layouts, 1.9 MB of HTML
```

**The headline number is 73 of 147.** Estonian workflows touch half of the method vocabulary
that European DH objects use. The other 74 methods are the map's most interesting region.
(With the first ten workflows it was 61 of 147; the three newer ones added 12 methods.)

**The discovered layout partly recovers TaDiRAH's own hierarchy.** Colour by "TaDiRAH goal"
and the Storage methods (Preserving, Cataloging, Organizing, Preservation Metadata, Storing)
sit together, as do the Capture methods, without anything in the layout knowing the taxonomy
exists — it is computed purely from co-occurrence. Where the discovered clusters *disagree*
with the hand-built goal groups is where practice and taxonomy have drifted apart.

## Run

```bash
pip install scikit-learn umap-learn hdbscan pyyaml numpy scipy   # hdbscan optional
cd method-galaxy
python 1_harvest.py       # SSHOMP (~1 min) + ETKAD pages
python 2_extract.py       # ET -> EN vocabulary join
python 3_layout.py        # 2 spaces x 3 metrics
python 4_build_map.py     # -> method_galaxy.html
```

Everything is pure HTTP into memory. No clones, no working trees, ~2.5 MB of JSON on disk.

## Design decisions worth knowing

**Why the Marketplace.** It is the only DH registry I found that is (a) large, (b) openly
queryable without auth, and (c) tagged with the *same* controlled vocabulary ETKAD uses.
`tadirah2` is one of its 15 vocabularies. Coverage is 72% on workflows and 65% on tools; it
falls to 38% across the whole corpus because datasets and publications are largely untagged.

**The vocabulary join had to be built by hand.** TaDiRAH's SKOS at `vocabs.dariah.eu`
publishes `"languages": ["en"]` — English labels only. ETKAD's Estonian terms are a local
translation, so `ET2EN` in `2_extract.py` is the bridge, checked term by term against the 147
labels actually present in the Marketplace. Two Estonian terms have no TaDiRAH2 counterpart:
`kauguse mõõtmine` (distance measures, present in TaDiRAH v1 and dropped in v2) and
`eemaldamine` (removing). Those are kept and reported rather than silently dropped — a term
local practice needed and the standard does not have is a small piece of evidence in itself.

**Three distance metrics, because they disagree usefully.** PPMI asks "do these co-occur more
than chance?", raw cosine asks "do these co-occur a lot?", Jaccard asks "how much do their
item sets overlap, regardless of size?". The defaults are chosen per space: on 147 methods
PPMI over-smooths into 2 giant clusters, while raw co-occurrence resolves 17 recognisable
families (OCR/recognition, audiovisual capture, discovery, identifiers, curation). The object
space is the opposite — large and dominated by ubiquitous methods, so PPMI is what gives it
shape. Switch metrics in the left rail and watch which groupings survive; the ones that do
are the robust ones.

**Cluster labels are computed from Marketplace titles only.** Including the ETKAD titles
put fragments of Estonian words into the labels: ten documents out of 2,376 dominated c-TF-IDF
because their vocabulary appears nowhere else in the corpus.

## Honest limitations

- **The gap report measures tagging, not practice.** A method counts as unused only when no
  ETKAD page carries its term. Several "unused" entries are plainly done in Estonia and simply
  untagged — the photo-archive workflow surely involves *Imaging*, and transcription happens
  across the corpus. This is not a flaw to apologise for; it is the argument. Discovery runs
  on what was declared, not on what was done.
- **The object space compares unlike things.** ETKAD workflows carry 8–20 methods each because
  they are workflows; most Marketplace entries are single-purpose tools with 1–3. So the
  Estonian dots cluster together partly for a structural reason rather than an intellectual
  one. The **method space is the fairer comparison** — use the object space for the
  recommender, not for "where does Estonia sit".
- **n = 13 on the Estonian side.** Every statement about Estonian practice here is about thirteen
  workflows from one hackathon-and-course pipeline, not about Estonian DH.
- **147 methods is the whole vocabulary, not the whole discipline.** TaDiRAH2 has no term for
  several things these workflows clearly do.
- **The translation is mine, not authoritative.** A term-by-term review by someone who owns
  the Estonian vocabulary would be worth doing before any of this is published.

## Things worth trying next

- Contribute ETKAD's staged workflows to the Marketplace. Its data model has a **`step`
  category with zero items in it** — the structure exists and nobody has populated it, and
  ETKAD's per-stage TaDiRAH tagging is exactly what it was designed for.
- Add EMS (the Estonian subject thesaurus, already linked on the ETKAD pages with persistent
  IDs) as a second axis, so the map can be sliced by subject as well as by method.
- Pull the tools named in the ETKAD workflow prose (RStudio, spaCy, Claude, QGIS…) into a
  structured field, and the tool layer from `workflow-galaxy` can be joined onto this one.
