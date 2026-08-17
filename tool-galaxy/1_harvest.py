#!/usr/bin/env python3
"""Stage 1: harvest the workflow corpus — disk-safe, streaming, resumable.

WHY THIS FILE IS WRITTEN THIS WAY
---------------------------------
The first attempt died by cloning a 963 MB repo without checking free space,
which filled the sandbox so completely that even `rm -rf` could no longer run.
Four structural defences now make that failure mode impossible:

1. STREAMING. Each repo is cloned, its handful of useful files copied out, and
   the clone deleted immediately — inside a try/finally, so it is removed even
   on crash or Ctrl-C. Peak disk is ONE repo, not ninety.
2. SPARSE CHECKOUT. Big repos are fetched with --filter=blob:none plus a sparse
   path spec, so git downloads only the files we actually read (.ga, meta.yml,
   modules.json) instead of the whole tree.
3. BUDGET GUARD. Free space is checked before every clone, and the harvest
   aborts cleanly while there is still headroom rather than at zero.
4. RESUMABLE. Extracted output is tiny JSON in work/raw/. Anything already
   harvested is skipped, so an abort costs only the current repo.

Total footprint of the finished harvest is a few MB of JSON — the repos do not
stick around.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager

WORK = os.path.abspath(os.environ.get("WFGAL_WORK", "./work"))
RAW = os.path.join(WORK, "raw")

MIN_FREE_GB = float(os.environ.get("WFGAL_MIN_FREE_GB", 2.0))   # abort below this
CLONE_TIMEOUT = 240

NFCORE = """
rnaseq sarek atacseq chipseq methylseq ampliseq mag viralrecon eager funcscan
taxprofiler differentialabundance fetchngs hic cutandrun circrna proteomicslfq
nanoseq smrnaseq scrnaseq dualrnaseq rnafusion rnasplice bacass bactmap bamtofastq
clipseq crisprseq demultiplex denovotranscript detaxizer epitopeprediction airrflow
hlatyping isoseq mhcquant metatdenovo nascent nanostring pangenome
pathogensurveillance phyloplace proteinfold raredisease readsimulator references
riboseq sammyseq scdownstream seqinspector spatialvi variantbenchmarking
viralintegration genomeannotator drop createtaxdb callingcards multiplesequencealign
molkart metaboigniter marsseq lncpipe imcyto hgtseq deepvariant coproid seqnado
tfactivity variantcatalogue phaseimpute pixelator lsmquant metapep mnaseseq
oncoanalyser pdxanalysis quantms radseq rangeland reportho rnadnavar scflow
scnanoseq slamseq stableexpression tbanalyzer tumourevo genomeqc gwas hicar
diaproteomics ddamsproteomics cageseq fastquorum
""".split()


# --------------------------------------------------------------------------
# disk safety
# --------------------------------------------------------------------------
def free_gb(path: str = None) -> float:
    return shutil.disk_usage(path or os.path.dirname(WORK) or ".").free / 1e9


def _chmod_retry(func, path, _exc):
    """Windows marks git pack/object files read-only; rmtree then raises
    PermissionError on them. Clear the flag and retry the delete."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def rmtree_hard(path: str) -> None:
    """Delete a tree, defeating Windows read-only git objects.

    plain rmtree(ignore_errors=True) SILENTLY leaves clones behind on Windows,
    which breaks the one-repo-peak-footprint guarantee without any warning.
    """
    kw = ({"onexc": _chmod_retry} if sys.version_info >= (3, 12)
          else {"onerror": _chmod_retry})
    try:
        shutil.rmtree(path, **kw)
    except OSError:
        shutil.rmtree(path, ignore_errors=True)
    if os.path.isdir(path):
        print(f"    !! FAILED to delete {path} — remove it manually before continuing")


def guard(stage: str) -> None:
    f = free_gb()
    if f < MIN_FREE_GB:
        print(f"\n!! only {f:.2f} GB free (floor {MIN_FREE_GB} GB) — stopping at {stage}.")
        print("   Harvest is resumable: fix disk space and re-run to continue.")
        sys.exit(2)


@contextmanager
def temp_clone(url: str, sparse: str = None, depth: int = 1,
               tree_only: bool = False, blobless: bool = True,
               timeout: int = None):
    """Clone into a temp dir, hand back the path, ALWAYS delete it afterwards.

    sparse: a git sparse-checkout pattern. When given, uses a partial clone so
    only matching blobs are downloaded — the difference between 900 MB and a
    few MB on repos like galaxyproject/training-material.

    tree_only: clone with --no-checkout and no working tree at all; read files
    out of the object store with ls_tree()/read_blobs(). Necessary on Windows —
    galaxyproject/iwc contains paths like `AB178040.1|2002.fasta` that NTFS
    cannot represent, and git aborts the ENTIRE checkout when it hits one, even
    under a sparse pattern that excludes it. That is why iwc silently yielded
    0 workflows; a tree-only read is immune to both that and MAX_PATH.
    """
    guard(url)
    tmo = timeout or CLONE_TIMEOUT
    tmp = tempfile.mkdtemp(prefix="wfgal_", dir=os.environ.get("WFGAL_TMP") or None)
    dest = os.path.join(tmp, "r")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    try:
        cmd = ["git", "-c", "core.longpaths=true", "clone",
               "--depth", str(depth), "--single-branch", "-q"]
        if (sparse or tree_only) and blobless:
            cmd += ["--filter=blob:none"]
        cmd += ["--no-checkout"] if tree_only else (["--sparse"] if sparse else [])
        cmd += [url, dest]
        subprocess.run(cmd, timeout=tmo, check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sparse and not tree_only:
            subprocess.run(["git", "sparse-checkout", "set", "--no-cone", sparse],
                           cwd=dest, timeout=tmo, check=True, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        yield dest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        yield None
    finally:
        rmtree_hard(tmp)   # runs even on exception / Ctrl-C; loud if it fails


def ls_tree(dest: str, suffix: str):
    """Paths in HEAD ending with `suffix` — read from the tree, no working copy."""
    r = subprocess.run(["git", "ls-tree", "-r", "HEAD", "--name-only"], cwd=dest,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=CLONE_TIMEOUT)
    return [p for p in r.stdout.splitlines() if p.endswith(suffix)]


def read_blobs(dest: str, paths):
    """Stream file contents out of the object store via `git cat-file --batch`.

    Strictly one request, one response. Queuing many requests before reading
    deadlocks: git blocks writing a large blob into a full stdout pipe, stops
    draining stdin, and we block writing the rest of the queue. On Windows that
    hangs silently and forever — it looked exactly like a slow network fetch.
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=dest, env=env,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    try:
        for q in paths:
            try:
                p.stdin.write(f"HEAD:{q}\n".encode("utf-8"))
                p.stdin.flush()
            except (BrokenPipeError, OSError):
                return
            header = p.stdout.readline().decode("utf-8", "replace").strip()
            if not header:
                return
            if header.endswith(("missing", "ambiguous")):
                continue
            try:
                size = int(header.split()[-1])
            except ValueError:
                continue
            body, left = b"", size
            while left > 0:                         # read() can return short
                chunk = p.stdout.read(left)
                if not chunk:
                    return
                body += chunk
                left -= len(chunk)
            p.stdout.read(1)                        # trailing newline
            yield q, body
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        p.stdout.close()
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()


def walk(root: str, suffix: str):
    for dirpath, _, files in os.walk(root):
        if ".git" in dirpath:
            continue
        for fn in files:
            if fn.endswith(suffix):
                yield os.path.join(dirpath, fn)


def done(tag: str) -> bool:
    return os.path.exists(os.path.join(RAW, tag + ".json"))


def save(tag: str, obj) -> None:
    with open(os.path.join(RAW, tag + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f)


# --------------------------------------------------------------------------
# harvesters — each writes small JSON, then the clone is discarded
# --------------------------------------------------------------------------
def harvest_nfcore_pipelines() -> int:
    n = 0
    for i, pipe in enumerate(NFCORE, 1):
        tag = "nfcore_" + pipe
        if done(tag):
            n += 1
            continue
        # Only modules.json is needed — sparse-fetch just that file.
        with temp_clone(f"https://github.com/nf-core/{pipe}.git",
                        sparse="modules.json") as d:
            if not d:
                continue
            mj = os.path.join(d, "modules.json")
            if not os.path.exists(mj):
                continue
            try:
                save(tag, {"pipeline": pipe, "modules_json": json.load(open(mj, encoding="utf-8"))})
                n += 1
            except Exception:
                pass
        if i % 15 == 0:
            print(f"    ...{i}/{len(NFCORE)} pipelines, {free_gb():.1f} GB free")
    return n


def harvest_galaxy(url: str, tag: str, sparse: str = None) -> int:
    if done(tag):
        return json.load(open(os.path.join(RAW, tag + ".json"), encoding="utf-8")).get("count", 0)
    out = []
    with temp_clone(url, tree_only=True) as d:
        if not d:
            print("    !! clone failed")
            return 0
        paths = ls_tree(d, ".ga")
        print(f"    {len(paths)} .ga files in tree", flush=True)
        for i, (path, body) in enumerate(read_blobs(d, paths), 1):
            if i % 50 == 0:
                print(f"    ...{i}/{len(paths)} read, {len(out)} usable", flush=True)
            try:
                g = json.loads(body.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(g, dict):
                continue
            tools = [str(s.get("tool_id")) for s in (g.get("steps") or {}).values()
                     if isinstance(s, dict) and s.get("tool_id")]
            if len(set(tools)) >= 3:
                out.append({"file": path,
                            "name": g.get("name") or os.path.basename(path),
                            "tool_ids": sorted(set(tools))})
    save(tag, {"count": len(out), "workflows": out})
    return len(out)


def _flat(v) -> str:
    """meta.yml writes `licence: [MIT]` and sometimes `doi: [a, b]`. str() on a
    list renders a Python repr, which then appeared verbatim in the map as
    `Licence: ['MIT']`."""
    if isinstance(v, (list, tuple, set)):
        return ", ".join(str(x) for x in v if x)
    return str(v or "")


def harvest_tool_metadata() -> int:
    """nf-core/modules meta.yml -> tool name, description, homepage, DOI, licence."""
    if done("toolmeta"):
        return len(json.load(open(os.path.join(RAW, "toolmeta.json"), encoding="utf-8")))
    import yaml
    meta = {}
    with temp_clone("https://github.com/nf-core/modules.git",
                    sparse="modules/nf-core/**/meta.yml") as d:
        if not d:
            return 0
        root = os.path.join(d, "modules", "nf-core")
        for f in walk(root, "meta.yml"):
            try:
                y = yaml.safe_load(open(f, encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(y, dict):
                continue
            top = os.path.relpath(f, root).split(os.sep)[0].lower()
            if top in meta:
                continue
            for entry in (y.get("tools") or []):
                if not isinstance(entry, dict):
                    continue
                for name, info in entry.items():
                    info = info if isinstance(info, dict) else {}
                    desc = (info.get("description") or "").strip().replace("\n", " ")
                    if not desc:
                        continue
                    meta[top] = {
                        "name": str(name), "description": desc[:600],
                        "homepage": info.get("homepage") or info.get("documentation") or "",
                        "doi": _flat(info.get("doi")),
                        "licence": _flat(info.get("licence")),
                    }
                    break
                if top in meta:
                    break
    save("toolmeta", meta)
    return len(meta)


# --------------------------------------------------------------------------
# GA4GH TRS harvest (WorkflowHub + Dockstore)
#
# Both registries implement TRS v2, so one client covers both. This is the path
# from ~570 workflows to several thousand. Nothing touches disk beyond the small
# JSON written at the end — descriptors are fetched into memory and parsed there.
#
# Per descriptor type, what we can actually recover:
#   GALAXY  the full .ga is served, so `tool_id` per step — as clean as IWC.
#   NFL     only main.nf is served (no module tree), so: `include ... from
#           'modules/nf-core/<tool>/...'`, bioconda specs and biocontainer image
#           names. Rich for DSL1 pipelines, thinner for DSL2.
#   CWL     `run:` step references, dockerPull images, baseCommand.
#   WDL     task/call names plus docker images.
#   SMK     `wrapper:` paths (v1.2/bio/<tool>/<sub>), conda env names, shell verbs.
# --------------------------------------------------------------------------
import re
import urllib.error
import urllib.parse
import urllib.request

TRS_TIMEOUT = 60
TRS_UA = {"User-Agent": "workflow-galaxy/1.0 (research prototype)",
          "Accept": "application/json"}

# Generic container/CLI noise that is not a scientific tool.
TRS_NOISE = {
    "ubuntu", "debian", "alpine", "centos", "bash", "sh", "python", "python3",
    "perl", "java", "r-base", "rocker", "conda", "mulled-v2", "biocontainers",
    "base", "busybox", "gawk", "awk", "sed", "grep", "cat", "cut", "sort",
    "head", "tail", "echo", "mkdir", "cp", "mv", "rm", "ln", "tar", "gzip",
    "gunzip", "zcat", "wget", "curl", "set", "true", "touch", "workflow",
    "main", "input", "output", "all", "common", "utils", "util", "config",
    "helper", "helpers", "local", "modules", "module", "subworkflow", "nf-core",
    "nfcore", "pipeline", "test", "tests", "docker", "singularity", "quay",
    "latest", "none", "null", "file", "files", "data", "tool", "tools",
}


def _trs_get(url: str, retries: int = 3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=TRS_UA)
            with urllib.request.urlopen(req, timeout=TRS_TIMEOUT) as r:
                return json.load(r), dict(r.headers)
        except Exception as e:                      # noqa: BLE001 - registry flakiness
            last = e
            if attempt < retries - 1:
                import time
                time.sleep(1.5 * (attempt + 1))
    raise last


def trs_list(root: str, limit: int = 100, max_items: int = 100000, **params):
    """Page through TRS /tools by following the next_page header.

    WorkflowHub treats `offset` as an item index and Dockstore as a page index;
    following next_page rather than computing offsets ourselves sidesteps that.
    """
    q = {"limit": limit, "offset": 0, **params}
    url = f"{root}/tools?" + urllib.parse.urlencode(q)
    out, seen_urls = [], set()
    while url and len(out) < max_items:
        page, headers = _trs_get(url)
        if not page:
            break
        out.extend(page)
        nxt = headers.get("next_page") or headers.get("Next-Page")
        if not nxt or nxt in seen_urls:
            break
        seen_urls.add(nxt)
        url = nxt
    return out[:max_items]


# WDL/CWL step names are frequently verbs describing a pipeline action rather
# than a tool — `merge_replicates`, `gather_bams`, `version_info`. Dockstore is
# full of them, and they masquerade as tools that recur across one lab's
# pipelines. Container image names on the same step are the reliable signal.
TRS_VERB = re.compile(
    r"^(get|set|make|create|merge|split|write|read|check|gather|collect|finalize|"
    r"localize|version|test|run|copy|concat|count|sum|sort|filter|convert|parse|"
    r"extract|generate|prepare|summari[sz]e|validate|compute|calc|calculate|"
    r"update|fetch|load|save|print|plot|scatter|task|step|job|process|wrapper|"
    r"rename|move|delete|clean|init|setup|finish|start|stop|apply|combine)[_\-]")


def _clean_name(n: str) -> str:
    n = str(n or "").strip().strip("'\"").lower()
    n = re.sub(r"\.(cwl|wdl|nf|ya?ml|smk|py)$", "", n)
    n = re.sub(r"[:@=].*$", "", n)                  # strip version / digest
    n = re.sub(r"^[.\-_/]+|[.\-_/]+$", "", n)
    n = re.sub(r"_v?\d+(\.\d+)*$", "", n)           # trailing version token
    if len(n) < 3 or len(n) > 40:
        return ""
    if n in TRS_NOISE or n.isdigit() or not re.match(r"^[a-z][a-z0-9_.\-]*$", n):
        return ""
    if TRS_VERB.match(n):
        return ""
    return n


def _from_containers(text: str):
    """Container images and conda specs name tools remarkably reliably."""
    got = set()
    for m in re.finditer(r"biocontainers/([A-Za-z0-9_.\-]+)", text):
        got.add(_clean_name(m.group(1)))
    for m in re.finditer(r"bioconda::([A-Za-z0-9_.\-]+)", text):
        got.add(_clean_name(m.group(1)))
    for m in re.finditer(r"(?:dockerPull|docker|container)\s*[:=]\s*['\"]?"
                         r"([A-Za-z0-9_.\-/]+)", text):
        img = m.group(1).split("/")[-1]
        if "biocontainers" in m.group(1) or "/" in m.group(1):
            got.add(_clean_name(img))
    return {g for g in got if g}


def extract_from_descriptor(dtype: str, content: str):
    """-> (kind, names). kind 'galaxy' keeps raw tool_ids for norm_galaxy()."""
    if not content:
        return "generic", []

    if dtype == "GALAXY":
        try:
            g = json.loads(content)
        except Exception:
            return "generic", []
        ids = [str(s.get("tool_id")) for s in (g.get("steps") or {}).values()
               if isinstance(s, dict) and s.get("tool_id")]
        return "galaxy", sorted(set(ids))

    got = set()
    if dtype == "NFL":
        for m in re.finditer(r"from\s+['\"]([^'\"]+)['\"]", content):
            path = m.group(1)
            if "modules/nf-core/" in path:
                got.add(_clean_name(path.split("modules/nf-core/")[1].split("/")[0]))
            elif "modules/local/" in path:
                got.add(_clean_name(path.split("modules/local/")[1].split("/")[0]))
            elif "/modules/" in path:
                got.add(_clean_name(path.split("/modules/")[1].split("/")[0]))
        got |= _from_containers(content)
    elif dtype == "CWL":
        for m in re.finditer(r"run\s*:\s*['\"]?([A-Za-z0-9_.\-/]+\.cwl)", content):
            got.add(_clean_name(os.path.basename(m.group(1))))
        for m in re.finditer(r"baseCommand\s*:\s*\[?\s*['\"]?([A-Za-z0-9_.\-]+)",
                             content):
            got.add(_clean_name(m.group(1)))
        for m in re.finditer(r"SoftwareRequirement|specs?\s*:\s*.*?(?:bio\.tools|"
                             r"biotools:)([A-Za-z0-9_.\-]+)", content):
            if m.lastindex:
                got.add(_clean_name(m.group(1)))
        got |= _from_containers(content)
    elif dtype in ("WDL", "PLAIN_WDL"):
        for m in re.finditer(r"\b(?:call|task)\s+([A-Za-z0-9_.]+)", content):
            got.add(_clean_name(m.group(1).split(".")[-1]))
        got |= _from_containers(content)
    elif dtype in ("SMK", "SNAKEMAKE"):
        for m in re.finditer(r"wrapper\s*:\s*['\"]([^'\"]+)['\"]", content):
            parts = [p for p in m.group(1).split("/") if p]
            if "bio" in parts:
                i = parts.index("bio")
                if i + 1 < len(parts):
                    got.add(_clean_name(parts[i + 1]))
        for m in re.finditer(r"conda\s*:\s*['\"]?([A-Za-z0-9_.\-/]+\.ya?ml)", content):
            got.add(_clean_name(os.path.basename(m.group(1))))
        for m in re.finditer(r"shell\s*:\s*[\"']{1,3}\s*\{?\s*([A-Za-z][A-Za-z0-9_.\-]*)",
                             content):
            got.add(_clean_name(m.group(1)))
        got |= _from_containers(content)
    else:
        got |= _from_containers(content)
    return "generic", sorted(g for g in got if g)


def harvest_trs(root: str, tag: str, src: str, max_items: int = 100000,
                workers: int = 8, **list_params) -> int:
    """Harvest one TRS registry. Resumable at the registry level."""
    if done(tag):
        return json.load(open(os.path.join(RAW, tag + ".json"),
                              encoding="utf-8")).get("count", 0)
    from concurrent.futures import ThreadPoolExecutor

    print(f"    listing {root} ...")
    try:
        entries = trs_list(root, max_items=max_items, **list_params)
    except Exception as e:                          # noqa: BLE001
        print(f"    !! listing failed: {type(e).__name__}: {e}")
        return 0
    print(f"    {len(entries)} registry entries; fetching descriptors "
          f"({workers} threads)")

    def version_ids(v):
        """TRS registries disagree about what identifies a version in the path.

        WorkflowHub wants the version `id` ("1"); Dockstore wants the version
        *name* ("master") — its `id` is the full `#workflow/...:master` string,
        which 404s. Its own `url` field carries the right token after
        /versions/, so prefer that and fall back. Getting this wrong is silent:
        every descriptor 404s and the registry just looks empty.
        """
        cands = []
        url = str(v.get("url") or "")
        if "/versions/" in url:
            cands.append(urllib.parse.unquote(url.split("/versions/")[-1].split("/")[0]))
        for k in ("id", "name"):
            if v.get(k) is not None:
                cands.append(str(v[k]))
        out = []
        for c in cands:
            if c and c not in out:
                out.append(c)
        return out

    def one(t):
        vs = t.get("versions") or []
        if not vs:
            return None
        v = vs[-1]
        dtypes = v.get("descriptor_type") or []
        tid = urllib.parse.quote(str(t.get("id")), safe="")
        for dt in dtypes:
            d = None
            for cand in version_ids(v):
                vid = urllib.parse.quote(cand, safe="")
                try:
                    d, _ = _trs_get(
                        f"{root}/tools/{tid}/versions/{vid}/{dt}/descriptor",
                        retries=1)
                    break
                except Exception:                   # noqa: BLE001
                    d = None
            if d is None:
                continue
            kind, names = extract_from_descriptor(dt, (d or {}).get("content") or "")
            if len(set(names)) >= 3:
                return {"id": str(t.get("id")), "name": t.get("name") or str(t.get("id")),
                        "url": t.get("url") or "", "dtype": dt, "kind": kind,
                        "src": src, "tools": sorted(set(names)),
                        "description": (t.get("description") or "")[:400]}
        return None

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(one, entries), 1):
            if r:
                out.append(r)
            if i % 250 == 0:
                print(f"      ...{i}/{len(entries)} checked, {len(out)} usable")
    save(tag, {"count": len(out), "workflows": out})
    return len(out)


# --------------------------------------------------------------------------
# DIGITAL-HUMANITIES CORNER
#
# nf-core and Galaxy are life sciences almost end to end, so the map they
# produce is a bioinformatics map. DH has no workflow registry to harvest — its
# computational method record lives in Jupyter notebooks. So: treat a notebook
# as a workflow and its third-party `import` statements as tool declarations.
#
# This is deliberately a weaker signal than a Galaxy `tool_id`, and the fact
# that it is weaker is itself the finding. A DH region that is sparse, thinly
# described and poorly connected is the empirical form of the argument that
# provenance metadata does not infer itself.
# --------------------------------------------------------------------------
DH_QUERIES = [
    "topic:digital-humanities language:Jupyter+Notebook",
    "topic:digital-humanities language:Python",
    "topic:computational-humanities",
    "topic:cultural-analytics",
    "topic:digital-history",
    "topic:text-mining+topic:humanities",
    "topic:stylometry",
    "topic:corpus-linguistics language:Jupyter+Notebook",
    "topic:distant-reading",
    "topic:handwritten-text-recognition language:Jupyter+Notebook",
]

# Repos that are DH computational practice but are not reliably tagged. GitHub
# topic search alone is a poor proxy: the top-starred `digital-humanities`
# repos are mostly libraries and collection-browsing web apps, so the notebook
# corpora have to be named explicitly.
DH_SEEDS = [
    "melaniewalsh/Intro-Cultural-Analytics",
    "programminghistorian/ph-submissions",
    "GLAM-Workbench/trove-newspapers",
    "GLAM-Workbench/web-archives",
    "GLAM-Workbench/trove-harvester",
    "GLAM-Workbench/trove-books",
    "GLAM-Workbench/trove-images",
    "GLAM-Workbench/recordsearch",
    "GLAM-Workbench/digitalnz",
    "GLAM-Workbench/australian-commonwealth-hansard",
    "maps-as-data/MapReader",
    "Living-with-machines/DeezyMatch",
    "impresso/impresso-datalab-notebooks",
    "DHRI-Curriculum/text-analysis",
    "NewsEye/NLP-Notebooks-Newspaper-Collections",
    "NLS-Digital-Scholarship/collections-as-data",
    "NationalLibraryOfNorway/digital_tekstanalyse",
    "mchesterkadwell/named-entity-recognition",
    "GEODE-project/perdido-geoparsing-notebook",
    "KALMUS-Color-Toolkit/KALMUS",
    "JasonKessler/scattertext",
    "cltk/cltk",
    "sgsinclair/alta",
]

# Import names that are plumbing, not method. Third-party but content-free.
DH_NOISE = {
    "setuptools", "pip", "wheel", "pytest", "unittest", "mock", "six",
    "typing_extensions", "future", "attr", "attrs", "dotenv", "tqdm",
    "ipython", "ipywidgets", "jupyter", "notebook", "google", "colab",
    "IPython", "warnings", "pkg_resources", "importlib_metadata", "setuptools_scm",
    "__future__", "conf", "config", "settings", "utils", "util", "helpers",
    "src", "lib", "scripts", "test", "tests", "main", "app", "core",
    # Web-application frameworks. The GitHub `digital-humanities` topic is worn
    # by a lot of collection-browsing web apps as well as by analysis
    # notebooks; without this their view/model code buries the method tools.
    "django", "flask", "fastapi", "wtforms", "sqlalchemy", "pydantic",
    "starlette", "jinja2", "werkzeug", "celery", "rest_framework", "graphene",
    "wagtail", "tornado", "aiohttp", "uvicorn", "gunicorn", "psycopg2",
    "pymysql", "redis", "boto3", "click", "typer", "rich", "loguru",
    "models", "views", "forms", "urls", "admin", "apps", "serializers",
    "migrations", "middleware", "schemas", "routes", "api", "db", "database",
}

DH_ALIAS = {
    "bs4": "beautifulsoup4", "PIL": "pillow", "cv2": "opencv-python",
    "sklearn": "scikit-learn", "skimage": "scikit-image", "yaml": "pyyaml",
    "dateutil": "python-dateutil", "mpl_toolkits": "matplotlib",
    "sentence_transformers": "sentence-transformers", "umap": "umap-learn",
    "fitz": "pymupdf", "docx": "python-docx",
    "pdf2image": "pdf2image", "osgeo": "gdal", "cartopy": "cartopy",
    # NB: do NOT map torch->pytorch or pytesseract->tesseract. Both of those
    # PyPI names belong to unrelated projects (`tesseract` is an astronomy
    # package), so the alias would attach a wrong description to the node.
}


def extract_notebook_imports(text: str, is_notebook: bool):
    """Third-party top-level module names imported by a notebook / script.

    Regex rather than `ast`, because notebook cells routinely contain magics
    (`%pip install`), shell escapes and partial code that will not parse.
    """
    if is_notebook:
        try:
            nb = json.loads(text)
        except Exception:
            return []
        src = []
        for cell in (nb.get("cells") or []):
            if cell.get("cell_type") != "code":
                continue
            s = cell.get("source")
            src.append("".join(s) if isinstance(s, list) else str(s or ""))
        text = "\n".join(src)

    mods = set()
    for m in re.finditer(r"^\s*import\s+([A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*)",
                         text, re.M):
        for part in m.group(1).split(","):
            mods.add(part.strip().split(".")[0])
    for m in re.finditer(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import", text, re.M):
        mods.add(m.group(1).split(".")[0])
    # `%pip install spacy nltk` names tools even when the import is conditional
    for m in re.finditer(r"^\s*[!%]\s*(?:pip|pip3|python -m pip)\s+install\s+(.+)$",
                         text, re.M):
        for tok in m.group(1).split():
            if tok.startswith("-") or "/" in tok or tok.startswith("http"):
                continue
            mods.add(re.split(r"[=<>\[]", tok)[0].strip())

    out = set()
    for m in mods:
        m = m.strip()
        if not m or m in DH_NOISE or m in sys.stdlib_module_names:
            continue
        m = DH_ALIAS.get(m, m.lower())
        if len(m) < 2 or m in DH_NOISE:
            continue
        out.add(m)
    return sorted(out)


def _gh_search(query: str, per_page: int = 50):
    url = ("https://api.github.com/search/repositories?q="
           + query.replace(" ", "+") + f"&sort=stars&per_page={per_page}")
    try:
        d, _ = _trs_get(url, retries=2)
        return [(r["full_name"], r.get("stargazers_count", 0), r.get("size", 0))
                for r in d.get("items", [])]
    except Exception as e:                          # noqa: BLE001
        print(f"    !! search failed ({query}): {type(e).__name__}")
        return []


# Even a blob-less clone has to fetch every tree object, so a repo carrying
# hundreds of MB of images or corpora costs minutes while yielding two or three
# notebooks. Skipping them cut this stage from hours to about twenty minutes.
DH_MAX_REPO_MB = float(os.environ.get("WFGAL_DH_MAX_REPO_MB", 250))
DH_CLONE_TIMEOUT = int(os.environ.get("WFGAL_DH_CLONE_TIMEOUT", 75))


def harvest_dh(max_repos: int = None, max_files_per_repo: int = None) -> int:
    """Clone DH notebook repos tree-only and read imports out of the objects.

    Notebooks are large (they carry their outputs), and on a blob-less clone
    each one is a separate lazy fetch, so this stage is dominated by per-file
    network round trips at roughly a minute or two per repo. The caps keep a
    full run to about half an hour; raise them for a deeper crawl.
    """
    max_repos = max_repos or int(os.environ.get("WFGAL_DH_MAX_REPOS", 35))
    max_files_per_repo = max_files_per_repo or int(
        os.environ.get("WFGAL_DH_MAX_FILES", 40))
    if done("dh_notebooks"):
        return json.load(open(os.path.join(RAW, "dh_notebooks.json"),
                              encoding="utf-8")).get("count", 0)

    # Seeds are hand-picked notebook corpora and always go in, ahead of search
    # results. Sorting the combined list by stars pushed every seed past the
    # max_repos cut, and the highest-starred `digital-humanities` repos are
    # mostly libraries with no notebooks at all — the harvest returned nothing.
    seen = {f.lower() for f in DH_SEEDS}
    seeds = [(f, 10 ** 6) for f in DH_SEEDS]
    found, skipped = [], 0
    for q in DH_QUERIES:
        for full, stars, size_kb in _gh_search(q):
            if full.lower() in seen:
                continue
            seen.add(full.lower())
            # Only a guard against pathological repos. Notebook repos are big
            # precisely because notebooks carry their outputs, so a tight cap
            # here throws away the corpus we came for; the per-repo clone
            # timeout is the real protection against slow ones.
            if size_kb / 1000.0 > DH_MAX_REPO_MB:
                skipped += 1
                continue
            found.append((full, stars))
        import time
        time.sleep(7)                               # unauthenticated search: 10/min
    found.sort(key=lambda r: -r[1])
    repos = (seeds + found)[:max_repos]
    print(f"    {len(repos)} candidate DH repos ({len(seeds)} seeds always kept "
          f"+ {len(found)} from {len(DH_QUERIES)} topic queries; "
          f"{skipped} skipped as >{DH_MAX_REPO_MB:.0f} MB)")

    out = []
    for i, (full, _stars) in enumerate(repos, 1):
        guard(full)
        # Blob-less: a DH repo averages only a couple of notebooks, so fetching
        # those few blobs on demand is far cheaper than pulling a 100 MB pack
        # for each of ninety repos. (Pulling full packs made this stage take
        # about two hours instead of fifteen minutes.)
        with temp_clone(f"https://github.com/{full}.git", tree_only=True,
                        timeout=DH_CLONE_TIMEOUT) as d:
            if not d:
                continue
            # Notebooks only. Including .py swept in the application source of
            # DH web apps, whose imports are Django views and SQLAlchemy models
            # rather than method tools. A notebook is the DH analogue of a
            # workflow; a views.py is not.
            paths = [p for p in ls_tree(d, ".ipynb")
                     if ".ipynb_checkpoints" not in p][:max_files_per_repo]
            # A repo importing its own package tells us nothing about tool
            # co-usage, and those self-imports otherwise rank near the top.
            own = re.sub(r"[^a-z0-9]", "", full.split("/")[-1].lower())
            for path, body in read_blobs(d, paths):
                if len(body) > 4_000_000:           # runaway notebook output
                    continue
                mods = extract_notebook_imports(body.decode("utf-8", "replace"),
                                                path.endswith(".ipynb"))
                mods = [m for m in mods
                        if re.sub(r"[^a-z0-9]", "", m) not in (own, own + "s")]
                if len(mods) >= 3:
                    out.append({"repo": full, "file": path,
                                "name": f"{full}/{os.path.basename(path)}",
                                "url": f"https://github.com/{full}/blob/HEAD/{path}",
                                "src": "dh-notebooks", "tools": mods})
        if i % 10 == 0:
            print(f"    ...{i}/{len(repos)} repos, {len(out)} notebooks, "
                  f"{free_gb():.1f} GB free")
    save("dh_notebooks", {"count": len(out), "workflows": out})
    return len(out)


def harvest_pypi_meta() -> int:
    """Descriptions for DH tools. There is no bio.tools for the humanities, so
    PyPI is the closest thing to a registry with descriptions and licences."""
    if done("dhmeta"):
        return len(json.load(open(os.path.join(RAW, "dhmeta.json"), encoding="utf-8")))
    p = os.path.join(RAW, "dh_notebooks.json")
    if not os.path.exists(p):
        return 0
    from concurrent.futures import ThreadPoolExecutor
    names = collections_counter_names(p)
    print(f"    querying PyPI for {len(names)} DH tool names")

    def one(n):
        try:
            d, _ = _trs_get(f"https://pypi.org/pypi/{urllib.parse.quote(n)}/json",
                            retries=1)
        except Exception:                           # noqa: BLE001
            return None
        info = d.get("info") or {}
        desc = (info.get("summary") or "").strip()
        if not desc:
            return None
        urls = info.get("project_urls") or {}
        doi = ""
        for k, v in urls.items():
            if "doi" in str(k).lower() or "doi.org" in str(v):
                doi = str(v).split("doi.org/")[-1]
                break
        return n, {"name": info.get("name") or n, "description": desc[:600],
                   "homepage": info.get("home_page") or urls.get("Homepage")
                   or f"https://pypi.org/project/{n}/",
                   "doi": doi, "licence": (info.get("license") or "")[:40]}

    meta = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(one, names):
            if r:
                meta[r[0]] = r[1]
    save("dhmeta", meta)
    return len(meta)


def collections_counter_names(path: str):
    import collections as _c
    c = _c.Counter()
    for w in json.load(open(path, encoding="utf-8"))["workflows"]:
        c.update(w["tools"])
    return [n for n, k in c.items() if k >= 2]


def main_dh() -> None:
    os.makedirs(RAW, exist_ok=True)
    print("Digital-humanities corner (notebook imports as tool declarations)")
    n = harvest_dh()
    print(f"      -> {n} notebooks with >=3 third-party imports")
    print(f"      -> {harvest_pypi_meta()} DH tools described from PyPI")


def main_trs() -> None:
    os.makedirs(RAW, exist_ok=True)
    print("GA4GH TRS harvest (in-memory; no disk footprint beyond JSON)")
    n = harvest_trs("https://workflowhub.eu/ga4gh/trs/v2", "trs_workflowhub",
                    "workflowhub")
    print(f"      -> WorkflowHub: {n} workflows with >=3 tools")
    # Dockstore lists ~6,300 workflows but pages slowly (tens of seconds per
    # 100), so a full crawl is a multi-hour job. Raise WFGAL_DOCKSTORE_MAX if
    # you have the time; the default keeps a full run to a sensible length.
    n = harvest_trs("https://dockstore.org/api/ga4gh/trs/v2", "trs_dockstore",
                    "dockstore", max_items=int(os.environ.get("WFGAL_DOCKSTORE_MAX",
                                                              1500)),
                    toolClass="Workflow")
    print(f"      -> Dockstore: {n} workflows with >=3 tools")


# --------------------------------------------------------------------------
def main() -> None:
    os.makedirs(RAW, exist_ok=True)
    print(f"work dir : {WORK}")
    print(f"disk     : {free_gb():.1f} GB free (floor {MIN_FREE_GB} GB)")
    guard("startup")

    print("\n[1/3] tool metadata (nf-core/modules, sparse meta.yml)")
    print(f"      -> {harvest_tool_metadata()} tools with descriptions")

    print(f"\n[2/3] nf-core pipelines (sparse modules.json, {len(NFCORE)} repos)")
    print(f"      -> {harvest_nfcore_pipelines()} pipelines")

    print("\n[3/3] Galaxy workflow collections (blob-less clone, tree-only read)")
    a = harvest_galaxy("https://github.com/galaxyproject/iwc.git", "galaxy_iwc")
    print(f"      -> iwc: {a} workflows")
    b = harvest_galaxy("https://github.com/galaxyproject/training-material.git",
                       "galaxy_tm")
    print(f"      -> training-material: {b} workflows")

    size_mb = sum(os.path.getsize(os.path.join(RAW, f)) for f in os.listdir(RAW)) / 1e6
    print(f"\nharvest complete — {len(os.listdir(RAW))} files, {size_mb:.1f} MB, "
          f"{free_gb():.1f} GB free")


# --------------------------------------------------------------------------
# FURTHER EXTENSION: for full step-level detail on WorkflowHub entries whose TRS
# descriptor is only the top-level file (NFL/SMK expose main.nf / Snakefile but
# not the module tree), fetch the RO-Crate zip from
#   https://workflowhub.eu/workflows/{id}/ro_crate?version={v}
# and read it IN MEMORY with zipfile.ZipFile(io.BytesIO(...)) — pull
# SoftwareApplication / SoftwareSourceCode entities and Workflow Run Crate
# `instrument` fields. Never unpack crates to disk; that is how this broke.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    if "--trs" in sys.argv:
        main_trs()
    elif "--dh" in sys.argv:
        main_dh()
    elif "--all" in sys.argv:
        main()
        print()
        main_trs()
        print()
        main_dh()
    else:
        main()
