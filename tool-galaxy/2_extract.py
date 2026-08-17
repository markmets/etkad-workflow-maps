#!/usr/bin/env python3
"""Stage 2: build workflow -> tool incidence from the harvested JSON.

Reads only work/raw/*.json (a few MB). The cloned repos are long gone by this
point — stage 1 deletes each one as soon as it has copied out what it needs.

VERIFIED on a 169-workflow subset: 702 distinct tools, 284 in >=2 workflows,
910 tools with description/homepage/DOI.

Output: work/corpus.json
"""
import collections
import glob
import json
import os
import re

WORK = os.path.abspath(os.environ.get("WFGAL_WORK", "./work"))
RAW = os.path.join(WORK, "raw")

# Infrastructure/plumbing, not science. Left in, these dominate the layout: the
# first run had utils_nextflow_pipeline, compose_text_param, cut1 and awk_tool
# inside the top 12 tools by frequency, which flattens all real structure.
STOPLIST = {
    "utils_nextflow_pipeline", "utils_nfcore_pipeline", "utils_nfschema_plugin",
    "utils_nfvalidation_plugin", "utils_pipeline", "pipeline_initialisation",
    "custom", "untar", "unzip", "gunzip", "cat", "tar", "mv", "cp",
    "compose_text_param", "param_value_from_file", "pick_value", "map_param_value",
    "collapse_dataset", "collection_element_identifiers", "split_file_to_collection",
    "cut1", "awk_tool", "find_and_replace", "add_a_column1", "filter1", "sort1",
    "join1", "comp1", "cat1", "paste1", "grep1", "wc_gnu", "sed_tool",
    "text_processing", "datamash_ops", "column_maker", "mergecols1", "addvalue",
    "regex1", "random_lines1", "head_tool", "tail_tool", "uniq_tool",
    "relabel_from_file", "tag_from_file", "unlabeled",
    # Galaxy built-ins and bgruening/text_processing, surfaced once WorkflowHub
    # was added. `Cut1` at 128 workflows and `Remove beginning1` at 49 would
    # otherwise outrank every real tool except multiqc.
    "remove beginning1", "show beginning1", "show tail1", "select first1",
    "select last1", "convert characters1", "summary_statistics1", "grouping1",
    "count1", "regexcolumn1", "condense characters1", "changecase",
    "trimmer", "secure_hash_message_digest", "table_compute",
    "tabular_to_csv", "csv_to_tabular", "tab2param", "param_text",
    "grep_tool", "cut_tool", "replace_in_line", "sort_header_tool",
    "sorted_uniq", "easyjoin", "multijoin", "unfold_columns", "merge_cols",
    "reverse", "tac", "sort_rows", "sort_list",
    # generic-descriptor plumbing (CWL/WDL/NFL/SMK side)
    "files_to_folder", "rename", "get-raw-files", "split-single-paired",
    "multiqc_hack", "copy", "move", "concat", "concatenate", "merge",
    "split", "compress", "decompress", "download", "upload", "checksum",
    "validate", "report", "summary", "index", "convert", "prepare",
    "check_input", "input_check", "samplesheet_check", "prepare_genome",
}

ALIAS_FIX = {
    "gatk4": "gatk", "samtool_filter2": "samtools", "bamtools_filter": "bamtools",
    "bwa_mem": "bwa", "star_fusion": "star", "rna_star": "star",
    "picard_markduplicates": "picard", "deeptools_bam_coverage": "deeptools",
    "bedtools_intersectbed": "bedtools", "vcffilter2": "vcflib",
    "seqtk_seq": "seqtk", "salmon_quant": "salmon", "kallisto_quant": "kallisto",
    "featurecounts": "subread", "htseq_count": "htseq",
}


def norm_galaxy(tool_id: str, known: set) -> str:
    """toolshed.g2.bx.psu.edu/repos/iuc/samtools_sort/... -> samtools"""
    if "/repos/" in tool_id:
        parts = tool_id.split("/repos/")[-1].split("/")
        nm = parts[2] if len(parts) > 2 else parts[-1]
    else:
        nm = tool_id
    nm = re.sub(r"^(tp_|__|toolshed_)", "", nm.lower())
    # Stoplist BEFORE the parent-collapse, not after. `tp_find_and_replace`
    # strips to `find_and_replace`, which is stoplisted — but the collapse rule
    # fired first and turned it into `find`, which is not, so a text-munging
    # step arrived in the top 15 tools wearing a different name.
    if nm in STOPLIST:
        return ""
    if nm in ALIAS_FIX:
        return ALIAS_FIX[nm]
    for sep in ("_", "-"):
        head = nm.split(sep)[0]
        if len(head) > 2 and head in known and head not in STOPLIST:
            return head          # collapse subtools onto a known parent
    return nm


# WDL/CWL step names that are pipeline actions, not tools. Stage 1 already
# drops the snake_case ones (`gather_bams`), but WDL convention is camelCase,
# which lowercases to a single run-on word — `gatherbqsrreports`,
# `concatclippedvcfchunks`, `getsampleidsfromvcf`. Those slipped through and
# formed entire clusters of GATK-Best-Practices task names masquerading as a
# tool domain. Matching the verb without requiring a separator catches them.
GENERIC_STEP = re.compile(
    r"^(gather|merge|concat|extract|get|set|collect|apply|split|index|filter|"
    r"make|create|write|read|check|finali[sz]e|locali[sz]e|validate|"
    r"summari[sz]e|aggregate|compute|calculate|convert|prepare|generate|"
    r"annotate|subset|sort|count|copy|move|rename|scatter|gatherer|update|"
    r"combine|select|assign|build|run|task|step)[a-z0-9]{3,}$")

# Bare words that carry no tool identity on their own.
GENERIC_WORD = {
    "runs", "task", "tasks", "can", "int", "sum", "flag", "wide", "against",
    "assemble", "consensus", "stats", "dedup", "align", "aligned", "metrics",
    "reference", "genome", "genomes", "sample", "samples", "output", "outputs",
    "results", "final", "temp", "tmp", "misc", "other", "value", "values",
    "params", "options", "args", "the", "and", "for", "with", "from", "into",
}


def norm_generic(name: str, known: set) -> str:
    """Normalise a TRS-derived tool name (container / include path / call name).

    Same collapse-onto-a-known-parent rule as norm_galaxy, so `samtools_sort`
    from a Snakemake wrapper and `samtools_sort` from a Galaxy tool_id land on
    the same node rather than becoming two neighbouring singletons.
    """
    nm = re.sub(r"^(tp_|__|toolshed_)", "", str(name or "").lower().strip())
    nm = re.sub(r"[^a-z0-9_.\-]", "", nm)
    if nm in STOPLIST or nm in GENERIC_WORD or GENERIC_STEP.match(nm):
        return ""
    if nm in ALIAS_FIX:
        return ALIAS_FIX[nm]
    if nm in known:
        return nm
    for sep in ("_", "-", "."):
        head = nm.split(sep)[0]
        if len(head) > 2 and head in known and head not in STOPLIST:
            return head
    return nm


def main() -> None:
    if not os.path.isdir(RAW):
        raise SystemExit(f"no harvest found at {RAW} — run 1_harvest.py first")

    meta_path = os.path.join(RAW, "toolmeta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    known = set(meta)      # nf-core names only — the collapse targets for norm_*
    print(f"tool metadata entries: {len(meta)} (nf-core meta.yml)")

    # PyPI descriptions for the DH side. Loaded after `known` is fixed on
    # purpose: DH package names must not become collapse targets for Galaxy
    # tool_ids, or e.g. `pandas`-prefixed ids would swallow unrelated tools.
    dhmeta_path = os.path.join(RAW, "dhmeta.json")
    if os.path.exists(dhmeta_path):
        dhmeta = json.load(open(dhmeta_path, encoding="utf-8"))
        for k, v in dhmeta.items():
            meta.setdefault(k, v)
        print(f"DH tool metadata entries: {len(dhmeta)} (PyPI)")

    wf_tools, wf_meta = {}, {}

    # --- nf-core: modules.json keys already name tools cleanly ---------------
    for f in sorted(glob.glob(os.path.join(RAW, "nfcore_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        pipe, mjson = d["pipeline"], d["modules_json"]
        tools = set()
        for repo_data in (mjson.get("repos") or {}).values():
            # `modules` only. The `subworkflows` section names composites like
            # fastq_align_star or bam_stats_samtools — pipeline plumbing one
            # level up, not tools, and redundant with the modules they contain.
            # Left in, they formed their own clusters and pulled real tools
            # (star, samtools) away from the tools they are actually used with.
            for mods in (repo_data.get("modules") or {}).values():
                for m in mods:
                    tools.add(m.split("/")[0].lower())
        tools = {ALIAS_FIX.get(t, t) for t in tools} - STOPLIST
        if len(tools) >= 3:
            wid = "nfcore:" + pipe
            wf_tools[wid] = tools
            wf_meta[wid] = {"name": "nf-core/" + pipe, "src": "nf-core",
                            "url": "https://nf-co.re/" + pipe}
    n_nf = len(wf_tools)

    # --- Galaxy -------------------------------------------------------------
    for tag, src in (("galaxy_iwc", "galaxy-iwc"), ("galaxy_tm", "galaxy-training")):
        p = os.path.join(RAW, tag + ".json")
        if not os.path.exists(p):
            continue
        for w in json.load(open(p, encoding="utf-8"))["workflows"]:
            tools = {norm_galaxy(t, known) for t in w["tool_ids"]
                     if not str(t).startswith("__")}
            tools = {t for t in tools if t and len(t) > 1} - STOPLIST
            if len(tools) >= 3:
                wid = f"{tag}:{w['file']}"
                wf_tools[wid] = tools
                wf_meta[wid] = {"name": w["name"], "src": src, "url": ""}

    n_gal = len(wf_tools) - n_nf

    # --- GA4GH TRS registries (WorkflowHub, Dockstore) ----------------------
    for p in sorted(glob.glob(os.path.join(RAW, "trs_*.json"))):
        tag = os.path.basename(p)[:-5]
        for w in json.load(open(p, encoding="utf-8"))["workflows"]:
            if w.get("kind") == "galaxy":
                tools = {norm_galaxy(t, known) for t in w["tools"]
                         if not str(t).startswith("__")}
            else:
                tools = {norm_generic(t, known) for t in w["tools"]}
            tools = {t for t in tools if t and len(t) > 1} - STOPLIST
            if len(tools) >= 3:
                wid = f"{tag}:{w['id']}"
                wf_tools[wid] = tools
                wf_meta[wid] = {"name": w.get("name") or w["id"],
                                "src": w.get("src", tag),
                                "url": w.get("url", "")}
    n_trs = len(wf_tools) - n_nf - n_gal

    # --- digital humanities: notebooks as workflows, imports as tools -------
    p = os.path.join(RAW, "dh_notebooks.json")
    if os.path.exists(p):
        for w in json.load(open(p, encoding="utf-8"))["workflows"]:
            tools = {t for t in w["tools"] if t and len(t) > 1} - STOPLIST
            if len(tools) >= 3:
                wid = "dh:" + w["file"] + "@" + w["repo"]
                wf_tools[wid] = tools
                wf_meta[wid] = {"name": w.get("name") or w["file"],
                                "src": "dh-notebooks", "url": w.get("url", "")}
    n_dh = len(wf_tools) - n_nf - n_gal - n_trs

    # --- de-duplicate mirrors ----------------------------------------------
    # Dockstore mirrors nf-core, WorkflowHub mirrors Galaxy training material.
    # Identical tool sets are almost always the same pipeline registered twice,
    # and duplicates inflate co-occurrence counts, which PPMI then treats as
    # real signal. Prefer the entry from the source with the richest metadata.
    RANK = {"nf-core": 0, "galaxy-iwc": 1, "galaxy-training": 2,
            "workflowhub": 3, "dockstore": 4, "dh-notebooks": 5}
    best = {}
    for wid, ts in wf_tools.items():
        key = frozenset(ts)
        cur = best.get(key)
        if cur is None or RANK.get(wf_meta[wid]["src"], 9) < RANK.get(wf_meta[cur]["src"], 9):
            best[key] = wid
    keep = set(best.values())
    dropped = len(wf_tools) - len(keep)
    wf_tools = {k: v for k, v in wf_tools.items() if k in keep}
    wf_meta = {k: v for k, v in wf_meta.items() if k in keep}
    print(f"de-duplicated {dropped} workflows with an identical tool set (registry mirrors)")

    counts = collections.Counter()
    for ts in wf_tools.values():
        counts.update(ts)

    by_src = collections.Counter(m["src"] for m in wf_meta.values())
    print("by source:", dict(by_src))
    print(f"workflows: {len(wf_tools)}  (pre-dedup {len(wf_tools) + dropped}; "
          f"harvested nf-core {n_nf}, galaxy {n_gal}, trs {n_trs}, dh {n_dh})")
    print(f"distinct tools: {len(counts)}")
    for th in (2, 3, 5, 10):
        print(f"  in >={th} workflows: {sum(1 for c in counts.values() if c >= th)}")
    print("top 15:", counts.most_common(15))

    json.dump(
        {"wf_tools": {k: sorted(v) for k, v in wf_tools.items()},
         "wf_meta": wf_meta, "meta": meta},
        open(os.path.join(WORK, "corpus.json"), "w"),
    )
    print(f"-> {os.path.join(WORK, 'corpus.json')}")


if __name__ == "__main__":
    main()
