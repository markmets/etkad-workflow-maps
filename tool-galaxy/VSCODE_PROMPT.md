# Prompt for Claude Code (VS Code)

Paste everything below the line into Claude Code, with `2026_ETKAD_workflow_space` (the project root) as the working directory.

---

Run the Workflow Galaxy pipeline in `workflow-galaxy/`. Read `workflow-galaxy/README.md` first — it has the design rationale and the measured numbers from a partial run.

**`cd workflow-galaxy` before running anything.** The scripts resolve their work dir as `./work` relative to the current directory, and `run_all.sh` uses `$(pwd)/work`. Running them from the project root would scatter `work/` and `galaxy_map.html` into the wrong place. All script paths below are relative to `workflow-galaxy/`.

**What it builds:** an Open Syllabus Galaxy–style interactive map where each dot is a software tool/library, and tools sit near each other when they're used together in the same scientific workflows. Clicking a dot shows the tool's description, method-paper DOI, and which workflows use it. Output is a single self-contained `galaxy_map.html`.

All four scripts are written. Stages 1–2 are verified on real data; stages 3–4 have **never been executed**. Work autonomously — don't ask me questions, make reasonable calls and tell me at the end.

## Critical: disk discipline

A previous session died by cloning a 963 MB repo without checking free space. It filled the disk so completely that even `rm -rf` could no longer run, which wedged the whole workspace irrecoverably. Do not repeat this.

- Check free space before any clone and after each stage. If free space drops below ~2 GB, stop and clean up rather than pushing on.
- `1_harvest.py` is already built to be safe — it clones one repo at a time, copies out the few files it needs, and deletes the clone in a `finally` block. Peak footprint is one repo. **Don't bypass it with ad-hoc `git clone` commands.**
- Never clone `research-software-ecosystem/content` (963 MB) in full. If you want bio.tools descriptions for the Galaxy-side nodes, use `--filter=blob:none --sparse` with a narrow path spec, verify the size first, and delete it immediately after extraction.
- If you fetch RO-Crate zips, read them in memory with `zipfile.ZipFile(io.BytesIO(...))`. Never unpack crates to disk.
- The harvest is resumable — output lands as small JSON in `work/raw/` and completed repos are skipped. Aborting costs only the current repo, so abort early rather than late.

## Windows environment notes

The earlier attempt ran on Linux. This is Windows, so expect these:

- **Already patched:** `1_harvest.py` now uses `rmtree_hard()` to force-delete read-only git objects. Plain `rmtree(ignore_errors=True)` silently leaves clones behind on Windows, breaking the one-repo-peak guarantee. If it ever prints `FAILED to delete`, stop and clear that temp dir before continuing.
- **Run this first:** `git config --global core.longpaths true`. `galaxyproject/training-material` has deeply nested paths that break at Windows' 260-char `MAX_PATH`. Note that `harvest_galaxy()` swallows clone errors and returns 0, so this failure looks like an empty result rather than an error — if `iwc` yields workflows and `training-material` yields 0, that's the cause.
- `python3` may not resolve on Windows (it can hit the Microsoft Store stub). Use `python` if so.
- `run_all.sh` needs Git Bash or WSL. If neither is available, run the stages directly — nothing in them needs shell features:
  `python 1_harvest.py && python 2_extract.py && python 3_layout.py && python 4_build_map.py`
- Deps: `pip install scikit-learn umap-learn hdbscan pyyaml numpy scipy`. Drop the `--break-system-packages` flag in `run_all.sh` — that's a Debian-ism, unnecessary here.
- If `hdbscan` won't install (it has historically needed MSVC build tools on Windows), swap to `sklearn.cluster.HDBSCAN` from scikit-learn ≥1.3 in `3_layout.py`. Compatible API, drops the dependency.

## Steps

1. Run the pipeline.
2. When it finishes, **open `galaxy_map.html` and actually look at it** — take a screenshot or read the generated `work/layout.json`. Don't just report that it ran.
3. **Verify cluster coherence.** Do `bwa` / `samtools` / `gatk` land near each other? Do the c-TF-IDF cluster labels describe recognisable domains (variant calling, assembly, RNA-seq, proteomics)? If clusters look like noise, the tool-name normalisation in `2_extract.py` is leaking — check `STOPLIST` and `norm_galaxy()`.
4. **Sanity-check the numbers** against the verified baseline: 169 workflows previously gave 702 distinct tools / 284 in ≥2 workflows. The full corpus (~90 nf-core pipelines + ~480 Galaxy workflows) should give substantially more. If it gives fewer, something broke in harvesting.

## With leftover time, in priority order

1. **More workflows.** The old sandbox could reach `github.com` but not `workflowhub.eu`, `dockstore.org`, `zenodo.org` or `raw.githubusercontent.com`. On a normal machine these are probably reachable — re-test. If WorkflowHub or Dockstore are reachable, harvest via GA4GH TRS (`/ga4gh/trs/v2/tools`); the client is stubbed in a comment block at the bottom of `1_harvest.py`. That's the path from ~570 workflows to 5k+ and would make the map genuinely dense.
2. **Tune the layout.** `TEXT_WEIGHT` and `MIN_WORKFLOWS` in `3_layout.py` are guesses. If clusters are blobby, try `MIN_WORKFLOWS=3` and a lower `TEXT_WEIGHT`.
3. **Features:** colour-by-source toggle (nf-core vs Galaxy), a "show only tools with a DOI" filter, edge-drawing between the selected tool and its top co-occurring tools.
4. **A digital-humanities corner.** nf-core and Galaxy are almost entirely life sciences, so this will be a bioinformatics map. An earlier version of `2_extract.py` had an `extract_notebook_imports()` sketch — it is *not* in the current file, so you'd be writing it fresh. The approach: clone DH notebook repos and treat `import` statements as tool declarations. Even a sparse DH corner is informative — and its sparseness is itself a finding worth showing.

## Context

This is exploratory work for HumAL / ETKAD, a research-workflow publication system for Estonian humanities researchers (see `Jaanuse_ideed_juuni.txt` in the project root). The map is a prototype of the discovery layer its Registry would need. Relevant constraint from that doc: RO-Crate won't infer good discovery metadata on its own, so tools with thin metadata clustering into an unplaceable blob is an expected and useful result, not a bug.
