#!/usr/bin/env bash
# Workflow Galaxy — full pipeline.
#
# Disk-safe by construction: stage 1 clones one repo at a time, reads the few
# files it needs straight out of the git object store, and deletes the clone
# immediately (in a finally block). Peak footprint is one repo; the finished
# harvest is a few MB of JSON. It also aborts cleanly if free space drops below
# WFGAL_MIN_FREE_GB.
#
# Run from THIS directory — work/ and galaxy_map.html are resolved relative to
# the current directory.
set -euo pipefail

export WFGAL_WORK="${WFGAL_WORK:-$(pwd)/work}"
export WFGAL_OUT="${WFGAL_OUT:-$(pwd)/galaxy_map.html}"
export WFGAL_MIN_FREE_GB="${WFGAL_MIN_FREE_GB:-2.0}"

# python3 does not resolve on Windows (it hits the Microsoft Store stub).
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python

echo "== disk before =="
df -h "$(dirname "$WFGAL_WORK")" | tail -1

echo "== deps =="
$PY -c "import sklearn, umap, yaml, numpy" 2>/dev/null || \
  pip install --quiet scikit-learn umap-learn hdbscan pyyaml numpy scipy
# hdbscan is optional: 3_layout falls back to sklearn.cluster.HDBSCAN, which
# avoids needing MSVC build tools on Windows.

# galaxyproject/training-material has paths past Windows' 260-char MAX_PATH.
git config --global core.longpaths true 2>/dev/null || true

# --all = github sources + GA4GH TRS registries + the DH notebook corner.
# Plain `1_harvest.py` is just the github sources; --trs and --dh run one each.
# Every stage is resumable — completed sources are skipped on a re-run.
echo "== 1/4 harvest (streaming, resumable) ==" && $PY 1_harvest.py --all
echo "== 2/4 extract ==" && $PY 2_extract.py
echo "== 3/4 layout  ==" && $PY 3_layout.py
echo "== 4/4 render  ==" && $PY 4_build_map.py

echo "== disk after =="
df -h "$(dirname "$WFGAL_WORK")" | tail -1
echo && echo "done -> $WFGAL_OUT"
