# Prompt for the new chat

Copy everything below the line into a fresh Cowork chat.

---

Run the Workflow Galaxy pipeline in `workflow-galaxy/` in my folder. All four scripts
are written; stages 1–2 are verified, stages 3–4 have never been executed. Work
autonomously for up to ~4 hours and don't ask me questions — make reasonable calls and
tell me at the end.

**What it builds:** an Open Syllabus Galaxy–style interactive map where each dot is a
software tool/library, and tools sit near each other when they're used together in the
same scientific workflows. Clicking a dot shows the tool's description, method-paper DOI,
and which workflows use it. Output is a single self-contained `galaxy_map.html`.

**Read `workflow-galaxy/README.md` first** — it has the design rationale and the measured
numbers from the partial run.

## Critical: disk discipline

A previous session died by cloning a 963 MB repo without checking free space. It filled
the sandbox so completely that even `rm -rf` could no longer run, which wedged the whole
workspace irrecoverably. Do not repeat this.

Rules:

- Run `df -h` before any clone and after each stage. If free space drops below ~2 GB, stop
  and clean up rather than pushing on.
- `1_harvest.py` is already built to be safe — it clones one repo at a time, copies out
  the few files it needs, and deletes the clone in a `finally` block. Peak footprint is one
  repo. **Don't bypass it with ad-hoc `git clone` commands.**
- Never clone `research-software-ecosystem/content` (963 MB) in full. If you want bio.tools
  descriptions for the Galaxy-side nodes, use `--filter=blob:none --sparse` with a narrow
  path spec, verify the size first, and delete it immediately after extraction.
- If you fetch RO-Crate zips, read them in memory with `zipfile.ZipFile(io.BytesIO(...))`.
  Never unpack crates to disk.
- The harvest is resumable — output lands as small JSON in `work/raw/` and completed repos
  are skipped. Aborting costs only the current repo, so abort early rather than late.

## Steps

1. `bash run_all.sh` (installs deps, runs all four stages).
2. When it finishes, **open `galaxy_map.html` and actually look at it** — take a screenshot
   or read the generated JSON. Don't just report that it ran.
3. Verify cluster coherence: do `bwa` / `samtools` / `gatk` land near each other? Do the
   c-TF-IDF cluster labels describe recognisable domains (variant calling, assembly, RNA-seq,
   proteomics)? If clusters look like noise, the tool-name normalisation in `2_extract.py`
   is leaking — check `STOPLIST` and `norm_galaxy()`.
4. Sanity-check the numbers against the verified baseline: 169 workflows previously gave
   702 distinct tools / 284 in ≥2 workflows. The full corpus (~90 nf-core pipelines +
   ~480 Galaxy workflows) should give substantially more. If it gives *fewer*, something
   broke in harvesting.
5. Save `galaxy_map.html` to my folder and show it to me.

## With leftover time, in priority order

1. **More workflows.** This sandbox can reach `github.com` but earlier could not reach
   `workflowhub.eu`, `dockstore.org`, `zenodo.org`, or `raw.githubusercontent.com` —
   re-test, since limits may differ. If WorkflowHub or Dockstore are reachable, harvest via
   GA4GH TRS (`/ga4gh/trs/v2/tools`); the client is stubbed at the bottom of `1_harvest.py`.
   That's the path from ~570 workflows to 5k+ and would make the map genuinely dense.
2. **Tune the layout.** `TEXT_WEIGHT` and `MIN_WORKFLOWS` in `3_layout.py` are guesses.
   If clusters are blobby, try `MIN_WORKFLOWS=3` and a lower `TEXT_WEIGHT`.
3. **Features:** colour-by-source toggle (nf-core vs Galaxy), a "show only tools with a
   DOI" filter, edge-drawing between the selected tool and its top co-occurring tools.
4. **A digital-humanities corner.** nf-core and Galaxy are almost entirely life sciences,
   so this will be a bioinformatics map. `extract_notebook_imports()` in the earlier version
   of `2_extract.py` sketched the approach: clone DH notebook repos and treat `import`
   statements as tool declarations. Even a sparse DH corner is informative — and its
   sparseness is itself a finding worth showing.

## Context

This is exploratory work for HumAL / ETKAD, a research-workflow publication system for
Estonian humanities researchers (see `Jaanuse_ideed_juuni.txt` in my folder). The map is a
prototype of the discovery layer its Registry would need. Relevant constraint from that
doc: RO-Crate won't infer good discovery metadata on its own, so tools with thin metadata
clustering into an unplaceable blob is an expected and useful result, not a bug.
