# ETKAD Workflow Maps — presentation notes

## The question

Open Syllabus Galaxy placed millions of reading-list items on a map: two books
sit close together because the same courses assign both. The underlying
mechanism — *co-occurrence becomes proximity* — can be applied to research
workflows instead of reading lists. The scale is very different: Open Syllabus
Galaxy had a million syllabi; this project has hundreds of workflows.

This was tested three times. Each attempt changed what a single dot on the map
represents.

---

## The three maps

| | A dot is | Built from | Answers |
|---|---|---|---|
| **Tool Galaxy** | a software tool | 1,138 bioinformatics workflows → 632 tools | which tools are used together |
| **Method Galaxy** | a method | 6,305 SSH Open Marketplace items, 2,366 tagged | which DH methods co-occur, and which ones are missing from Estonian practice |
| **Workflow Galaxy** | a workflow | 237 workflows from 3 sources | which workflows resemble each other, and in what respect |

**Tool Galaxy** applies the method to a field where machine-readable workflow
data already exists. Life sciences publish thousands of such workflows. The
resulting map recovers known clusters — RNA-seq, genome assembly, proteomics —
without being told they exist beforehand. It contains no humanities content;
its purpose is to test whether the underlying method works at all.

**Method Galaxy** places ETKAD's 10 workflows inside a larger, existing map,
because 10 workflows are not enough data to build a map from on their own. The
join is TaDiRAH, the method vocabulary HumAL already uses. Result: ETKAD uses
61 of 147 methods in the vocabulary; the other 86 are used elsewhere in Europe
but not documented in Estonian practice.

**Workflow Galaxy** compares whole workflows rather than tools or methods. Its
unit is the thing ETKAD actually publishes. The viewer chooses what "similar"
means: same methods, same software, same subject, or same shape of process.

### How the three relate

Conceptually, the three maps nest: a workflow is made of method-tagged steps,
and a step is sometimes carried out with a tool. Workflow Galaxy → Method
Galaxy → Tool Galaxy is a hierarchy of what a project does, not three
independent alternatives.

The underlying data does not nest the same way:

- **Tool Galaxy** shares no data with the other two maps. It draws on a
  separate field (bioinformatics) with no humanities content.
- **Method Galaxy** and **Workflow Galaxy** both draw on the SSH Open
  Marketplace and the same 10 ETKAD workflows, but at different grain. Method
  Galaxy covers the full method vocabulary across all 2,366 tagged Marketplace
  items. Workflow Galaxy covers a narrower slice — only the 108 Marketplace
  items structured as step-by-step workflows — and treats shared methods as
  one of seven comparison features rather than the whole measure.

---

## Where the workflows come from

| Source | Workflows | What it is |
|---|---|---|
| Programming Historian | 119 | every English-language lesson; a tutorial read as an ordered workflow |
| SSH Open Marketplace | 108 | every workflow object it holds — Europe's DH infrastructure registry |
| ETKAD / HumAL | 10 | all of ETKAD's published workflows |
| **Total** | **237** | |

This is the entire content of all three sources, not a sample. No larger
openly queryable DH workflow corpus sharing a controlled vocabulary currently
exists.

---

## How each map was built

**Tool Galaxy**

1. Queried the GA4GH TRS API (WorkflowHub, Dockstore) for workflow listings.
2. Read workflow files directly from git object stores, without a full
   checkout, so nothing large was downloaded.
3. Parsed Galaxy `.ga`, Nextflow, WDL and CWL files for the tools each step
   calls.
4. Normalised tool names (aliases, stoplist for generic steps).
5. Built a tool × workflow co-usage matrix → PPMI → SVD → UMAP → HDBSCAN
   clusters.

**Method Galaxy**

1. Harvested the SSH Open Marketplace REST API — 64 calls, 6,305 items,
   properties returned inline.
2. Scraped the 10 ETKAD workflow pages, reading controlled terms from the
   `data-type` attributes rather than inferring them from label text.
3. Hand-built an Estonian → English TaDiRAH bridge (78 terms), since the
   official vocabulary publishes English labels only and no such bridge
   existed.
4. Built a method × object matrix → three distance measures → SVD → UMAP.
5. Produced a gap report: which methods are used in Europe but not
   documented in Estonia.

**Workflow Galaxy**

1. Pulled the Marketplace `/workflows` endpoint — 108 workflows with 729
   ordered steps.
2. Scraped the Programming Historian lesson index plus each lesson's ordered
   section headings.
3. Re-parsed the ETKAD pages for per-stage TaDiRAH tags.
4. Built a 2,841-name software gazetteer from Marketplace tools and matched
   it case-sensitively against workflow prose, recovering names such as
   OpenRefine, QGIS, Palladio, EstNLTK and word2vec from unstructured
   Estonian text.
5. Represented each workflow as seven feature sets, weighted rare features
   more heavily, and compared workflows by cosine similarity.
6. Sent the feature vectors to the browser, so similarity weights recompute
   live as the viewer adjusts them.
7. Ran a held-out test to check whether the map's ordering is meaningful (see
   below).

---

## How representative is ETKAD's contribution?

ETKAD supplies 10 of 237 workflows (4% of the corpus) but 59 of the 272
per-stage method tags in the corpus (22% of the tagged evidence).

| Source | Workflows | Steps tagged in order |
|---|---|---|
| Programming Historian | 119 | 0 |
| SSH Open Marketplace | 108 | 213 (44% of them) |
| ETKAD / HumAL | 10 | 59 (90% of them) |

Per-stage method tagging is what makes "the shape of a workflow" computable.
Of the 44 workflows in the corpus with a usable shape, 9 are ETKAD's. On this
measure, ETKAD is the densest contributor in the corpus, not a small one.

Two things follow from this:

- Ten workflows are not a representative sample of Estonian digital
  humanities. They come from one hackathon-and-course pipeline, and the map
  should not be read as a description of the field as a whole.
- The map does not need ETKAD's workflows to be numerous, only well
  described. The surrounding 227 workflows do most of the positioning; that
  was the design.

---

## Extending the corpus

- **HumAL keeps publishing** — the only route that adds further Estonian
  workflows.
- **Programming Historian in Spanish, French and Portuguese** — roughly 200
  more lessons, many of them translations that would need de-duplication.
  Low effort.
- **Marketplace training materials** — 946 items, often step-structured, but
  the API does not expose their steps. Would need scraping.
- **The 1,138 bioinformatics workflows** — already harvested for Tool Galaxy
  and joinable to Workflow Galaxy. Would test whether "shape" as a similarity
  measure generalises across fields. Needs a second vocabulary bridge, kept
  separate from the one used today.

A complementary option is contributing data rather than collecting it: the
Marketplace's step model fits HumAL's staged workflows well, and few
Marketplace entries currently use it.

---

## What the held-out test found

The test: hide a fifth of a workflow's methods, rank its neighbours using one
comparison aspect at a time, and check whether the hidden methods are
recovered.

- **Step order predicts what a project does** (49% accuracy) — a better
  predictor than subject matter or wording, using no knowledge of workflow
  content.
- **Shared software predicts little** (31% accuracy) — below the 34% obtained
  by always guessing the most common methods. This suggests recommending
  workflows by shared tools alone is not reliable.
- **Interpretation tends to happen early**, before analysis, and discovery
  tends to precede data capture. This pattern comes from 53 workflows that do
  not follow a single fixed model — they behave as loops rather than
  pipelines.

## Limitations

- **The gap report measures tagging, not practice.** Some "unused" methods
  are likely used in Estonia but not documented in a workflow's metadata.
  This is a limitation of the underlying data, not a defect in the map:
  discovery can only run on what has been declared.
- **Distances on the map are not meaningful; adjacency is.** Which items are
  near each other is informative. How far apart two clusters appear is
  mostly a property of the layout algorithm, not the underlying data.

---

Technical method with a worked example: `workflow-galaxy/how_it_works.html`
