# Workflow Galaxy — Open Syllabus-style map of research workflow tools

An interactive map where **each dot is a software tool/library**, and tools sit near each
other when they are used together in the same workflows. Directly analogous to Open Syllabus
Galaxy, where dots are texts and proximity means co-assignment in the same courses.

    Open Syllabus:  course  assigns  text        -> co-assignment
    This project:   workflow  uses   tool        -> co-usage

## Status

All four stages run end to end. Output is a single self-contained `galaxy_map.html`.

| Stage | Script | Status |
|---|---|---|
| 1. Harvest corpus | `1_harvest.py` | github + GA4GH TRS + DH notebooks |
| 2. Extract tools + metadata | `2_extract.py` | reads `work/raw/`, normalises, de-duplicates |
| 3. Layout (PPMI -> SVD -> UMAP -> HDBSCAN) | `3_layout.py` | tuned |
| 4. Build interactive HTML | `4_build_map.py` | search, colour-by-source, DOI filter, edges |

### Measured results (full run, 2026-08-05)

Harvested, before normalisation:

| Source | Workflows | How tools are named |
|---|---|---|
| nf-core | 81 pipelines | `modules.json` module keys |
| Galaxy IWC | 112 | `.ga` step `tool_id` |
| Galaxy training-material | 305 | `.ga` step `tool_id` |
| WorkflowHub (TRS) | 750 | descriptor: GALAXY / CWL / NFL / SMK |
| Dockstore (TRS) | 673 of 1,500 listed | descriptor: WDL / CWL / NFL |
| DH notebooks | 119 | third-party `import` statements |

After normalisation and de-duplication of registry mirrors:

```
workflows:                 1,138   (1,679 before de-dup; 541 mirrors removed)
  nf-core 71 · galaxy-iwc 84 · galaxy-training 224
  workflowhub 258 · dockstore 404 · dh-notebooks 97

distinct tools:            3,542
tools in >=2 workflows:    1,179
tools in >=3 workflows:      632   <- the mapped nodes
tools in >=5 workflows:      258
tools in >=10 workflows:      95

map: 632 nodes, 32 clusters, 90 unclustered, 705 KB of HTML
tool metadata: 909 nf-core meta.yml entries + 50 PyPI entries
harvest on disk: 2.3 MB of JSON in 88 files
```

Against the earlier 169-workflow baseline (702 distinct tools, 284 in >=2 workflows), the
full corpus is 6.7x the workflows, 5.0x the distinct tools and 4.2x the nodes above the
>=2 threshold.

**Clusters are coherent.** `bwa`-`picard`-`samtools`-`gatk` sit together; the 32 clusters
resolve into recognisable domains — GATK best-practices variant calling, long-read assembly
(`minimap2`/`flye`/`spades`/`unicycler`/`bandage`), RNA-seq (`star`/`kallisto`/`rsem`/
`subread`), OpenMS proteomics (`xtandemadapter`/`peptideindexer`/`falsediscoveryrate`),
taxonomic profiling (`kraken2`/`krona`/`metaphlan`), AMR/bacterial genomics (`shovill`/
`abricate`/`bakta`/`prokka`/`amrfinderplus`), metagenome binning (`metabat2`/`maxbin2`/
`concoct`/`semibin`), amplicon (`mothur`), ChIP-seq (`macs2`/`deeptools`/`bedtools`),
viral surveillance (`nextclade`/`pangolin`/`vadr`), Nextstrain phylogenetics (`mafft`/
`augur`), bioimaging (`ip_*`) and two molecular-dynamics clusters (GROMACS and BioExcel
BioBB).

**The DH corner is a detached island.** All 32 DH nodes form a single cluster, 14.6 layout
units from the map centroid, sharing no tools whatsoever with the life-science mass. Inside
it the structure is right — `spacy` next to `en_core_web_sm`, `nltk`/`gensim`/`wordcloud`
adjacent. Switch the map to "Colour: source" to see it.

**Metadata coverage is the finding.** 194 of 632 nodes carry a description and 102 carry a
method-paper DOI — under a sixth of the map. Split by side:

```
                     nodes    described    with DOI
life sciences          600          163         102
DH notebooks            32           31           0
```

DH tools describe well (PyPI has summaries for nearly all of them) and cite not at all:
PyPI records no DOI for a single one. There is no humanities equivalent of nf-core
`meta.yml`'s method-paper link. Turn on "DOI only" and the DH island disappears entirely.
That is the concrete, visible version of the RO-Crate argument for HumAL/ETKAD: descriptive
metadata can be scraped, but the scholarly citation link has to be asserted by someone.


## Requirements

```bash
pip install scikit-learn umap-learn hdbscan pyyaml numpy scipy
```

`hdbscan` is optional — stage 3 falls back to `sklearn.cluster.HDBSCAN` (scikit-learn >= 1.3),
which matters on Windows where `hdbscan` wants MSVC build tools.

Needs only ~2 GB free disk. The harvester is streaming, so peak footprint is one repo at
a time and the finished harvest is a few MB of JSON.

## Run

```bash
bash run_all.sh          # all four stages, all sources
# or individually (use `python` if `python3` hits the Windows Store stub):
python 1_harvest.py          # github: nf-core + Galaxy IWC + Galaxy training
python 1_harvest.py --trs    # GA4GH TRS: WorkflowHub + Dockstore
python 1_harvest.py --dh     # digital-humanities notebook corner
python 1_harvest.py --all    # all three
python 2_extract.py
python 3_layout.py
python 4_build_map.py        # -> galaxy_map.html
```

Every source is resumable: harvested output lands as small JSON in `work/raw/` and completed
sources are skipped, so aborting costs only the source in flight.

### Tuning stage 3

All layout parameters read from the environment, so alternatives can be compared without
editing code:

```bash
WFGAL_MIN_WORKFLOWS=2 WFGAL_TEXT_WEIGHT=0.5 WFGAL_N_NEIGHBORS=15 python 3_layout.py
```

## Disk safety

The first attempt died by cloning a 963 MB repo without checking free space. The sandbox
filled so completely that even `rm -rf` could no longer run, wedging the workspace beyond
recovery. `1_harvest.py` makes that failure mode structurally impossible:

- **Streaming** — each repo is cloned, the few useful files are read out of the git object
  store, and the clone is deleted in a `finally` block. Peak disk is one repo, not ninety.
- **Partial clone** — `--filter=blob:none` fetches only the blobs actually read.
- **No working tree** — `--no-checkout` plus `git cat-file --batch`. Nothing is ever
  materialised on the filesystem, which also sidesteps every path-legality problem
  (see Windows notes below).
- **Budget guard** — free space is checked before every clone; the run aborts cleanly at
  `WFGAL_MIN_FREE_GB` (default 2.0) instead of at zero.
- **Resumable** — completed sources are skipped.
- **TRS and PyPI are pure HTTP** — descriptors are parsed in memory, never written down.

If you extend the harvester, keep these properties. Read RO-Crate zips in memory with
`zipfile.ZipFile(io.BytesIO(...))` rather than unpacking them.

## Design decisions worth knowing

**Why tools as nodes, not workflows.** Two reasons. Volume: even a few thousand workflows is
not many points for a map, but they contain far more distinct tools. Recognizability: Open
Syllabus works because everyone recognizes *Discipline and Punish*; nobody recognizes
"workflow #2172". Named tools (`bwa`, `samtools`, `spacy`) are recognizable in exactly the way
that matters.

**Why not citation coupling.** The obvious approach — link workflows via their associated
papers — fails on coverage. WorkflowHub lists **66 publications total** against 1,000+
workflows, and many of those 66 are papers *about* workflow infrastructure rather than papers
behind a specific pipeline. The tool-level view recovers the same "recognizable scholarly
object" property without needing publication links, because tools have canonical method
papers (nf-core `meta.yml` carries the DOI directly).

**PPMI weighting is not optional.** Raw co-occurrence puts `multiqc`, `samtools` and `fastqc`
at the centre of everything and flattens the structure. PPMI downweights ubiquity so that
co-occurrence carries information.

**Plumbing stoplist.** Extraction surfaces infrastructure, not just science:
`utils_nextflow_pipeline`, `compose_text_param`, `Cut1`, `Remove beginning1`, `tp_awk_tool`.
These dominate the layout if left in — `Cut1` alone appears in more workflows than any real
tool except `multiqc`. See `STOPLIST` in `2_extract.py`.

**The stoplist must be applied before name-collapsing, not after.** `tp_find_and_replace`
strips its Galaxy prefix to `find_and_replace`, which is stoplisted — but the
collapse-onto-a-known-parent rule fired first and rewrote it to `find`, which is not. A
text-munging step then arrived in the top 15 tools by frequency wearing a different name.
This is the failure mode to check first if clusters ever look like noise.

**nf-core `subworkflows` are not tools.** `modules.json` lists both; the subworkflow section
names composites like `fastq_align_star` and `bam_stats_samtools`. Left in, they formed their
own clusters and pulled real tools away from the tools they are actually used with. Stage 2
reads the `modules` section only.

**Registry mirrors are de-duplicated.** Dockstore mirrors nf-core and WorkflowHub mirrors
Galaxy training material, so the same pipeline is registered two or three times. Identical
tool sets are collapsed to one workflow, preferring the source with the richest metadata.
Without this, PPMI treats a mirrored pipeline as independent evidence of co-usage.

**Descriptor types give very unequal signal.** Galaxy `.ga` files name every tool per step and
are as good as it gets. Nextflow, CWL, WDL and Snakemake expose only their top-level file over
TRS, so tools have to be recovered from `include` paths, `run:` references, container image
names and conda specs. WDL is the weakest: `call` names are usually pipeline verbs
(`gather_bams`, `version_info`) rather than tools, which is why `TRS_VERB` in `1_harvest.py`
drops them and container images carry the load.

## The digital-humanities corner

nf-core, Galaxy, WorkflowHub and Dockstore are life sciences almost end to end, so on their
own they produce a bioinformatics map. DH has no workflow registry to harvest — its
computational method record lives in Jupyter notebooks. So `harvest_dh()` treats a notebook as
a workflow and its third-party `import` statements as tool declarations, over repos found by
GitHub topic search (`digital-humanities`, `cultural-analytics`, `stylometry`,
`distant-reading`, ...) plus a curated seed list.

Two things had to be constrained to make this useful:

- **Notebooks only, not `.py`.** The `digital-humanities` GitHub topic is worn by a lot of
  collection-browsing web applications as well as by analysis notebooks. Including their
  source made Django, Flask, SQLAlchemy and WTForms outrank spaCy and NLTK. A notebook is the
  DH analogue of a workflow; a `views.py` is not.
- **Self-imports dropped.** A repo importing its own package says nothing about tool co-usage.

Descriptions come from PyPI, which is the closest thing the humanities have to bio.tools.
It gives summaries, homepages and licences — but essentially **no DOIs**. That gap is the
finding: there is no DH equivalent of `meta.yml`'s method-paper link, so the DH region of the
map is the one place where "show only tools with a DOI" empties out. Building that mapping
would be a real contribution rather than a blocker.

## Known limitations

- **Domain skew remains.** The DH corner is real but small — 32 nodes against 600.
- **Dockstore is only partly crawled.** Its TRS listing pages slowly (tens of seconds per
  100, degrading under sustained use), so the default stops at 1,500 of ~6,300 workflows.
  Raise `WFGAL_DOCKSTORE_MAX` and allow several hours for the rest.
- **The DH repo list is partly luck.** GitHub's unauthenticated search API rate-limits hard,
  and several topic queries failed outright on the recorded run; the 23 curated seeds carried
  it. With a `GITHUB_TOKEN` the search side would be far more reliable.
- **DH co-usage is weaker evidence than a Galaxy `tool_id`.** An import is a much looser
  statement than a declared workflow step, and the DH region is correspondingly less
  structured. That the signal is weaker is itself part of the result.
- **Sparsity is a finding, not just a nuisance.** Tools with thin metadata cluster into a
  visible, unplaceable blob. That is the empirical version of the argument that RO-Crate does
  not infer good discovery metadata on its own — the relevant constraint for HumAL/ETKAD.
- **Most nodes still have no description.** nf-core `meta.yml` covers the nf-core side well
  and PyPI covers the DH side; Galaxy-only and container-derived tools have neither. Adding
  bio.tools would close much of this: clone `research-software-ecosystem/content` with
  `--filter=blob:none --sparse` on a narrow path spec, read `data/<tool>/<tool>.biotools.json`,
  and delete it immediately. Never clone that repo in full — it is 963 MB and is what killed
  the first attempt.

## Windows notes

Three Windows-specific failures cost real time here, all of which now have fixes in the code:

1. **`galaxyproject/iwc` silently yielded 0 workflows.** It contains paths like
   `AB178040.1|2002.fasta`; `|` is illegal on NTFS, and git aborts the *entire* checkout when
   it hits one — even under a sparse pattern that excludes it. `harvest_galaxy()` swallowed the
   clone error and returned 0, so it looked like an empty result rather than a failure. Fixed
   by never creating a working tree: `--no-checkout` plus `ls_tree()` / `read_blobs()`, which
   also removes the MAX_PATH problem in `galaxyproject/training-material`.
   Still run `git config --global core.longpaths true`.
2. **`git cat-file --batch` deadlocked.** Queuing many requests before reading responses
   hangs: git blocks writing a large blob into a full stdout pipe, stops draining stdin, and
   the writer blocks on a full stdin pipe. It looks exactly like a slow network fetch and
   never times out. `read_blobs()` is now strictly one request, one response.
3. **`shutil.rmtree(ignore_errors=True)` silently leaves clones behind**, because git marks
   pack/object files read-only. That breaks the one-repo-peak-footprint guarantee without any
   warning. `rmtree_hard()` clears the flag and retries, and prints loudly if a tree survives.

Also: `python3` may resolve to the Microsoft Store stub — use `python`. `run_all.sh` needs Git
Bash or WSL; nothing in the stages needs shell features, so they can be run directly.
