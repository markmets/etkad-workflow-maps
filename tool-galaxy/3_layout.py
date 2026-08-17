#!/usr/bin/env python3
"""Stage 3: turn tool co-usage into 2D coordinates + clusters.

Pipeline, and why each piece is there:

  incidence (tool x workflow)
    -> PPMI            ubiquitous tools (multiqc in 89/169 workflows, samtools in
                       56) otherwise sit at the centre of everything and flatten
                       all structure. PPMI downweights ubiquity so co-occurrence
                       actually carries information.
    -> TruncatedSVD    dense ~100d, denoises the very sparse count matrix
    -> hstack TF-IDF   descriptions from nf-core meta.yml, SVD'd too. Pure
                       co-occurrence strands rare/one-off tools as singletons;
                       text guarantees every node lands somewhere sensible.
    -> UMAP(cosine)    2D
    -> HDBSCAN         clusters
    -> c-TF-IDF        cluster labels from distinctive tool names + description
                       terms (the BERTopic trick)

Output: work/layout.json
"""
import collections
import json
import os

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

WORK = os.path.abspath(os.environ.get("WFGAL_WORK", "./work"))
# Tunable from the environment so alternatives can be compared without edits.
# Defaults below are the tuned values, chosen by comparing rendered maps.
#   MIN_WORKFLOWS 2 -> 3   at 2 the map is mostly one-off tools; UMAP flings
#                          them outward and squashes the real structure.
#   TEXT_WEIGHT 0.5 -> 0.3 most nodes have no description at all, so a heavy
#                          text term mainly separated described from
#                          undescribed tools rather than domain from domain.
#   N_NEIGHBORS 15 -> 10   the sequencing core is densely inter-connected
#                          (multiqc/samtools/fastqc appear nearly everywhere).
#                          At 30, HDBSCAN returned ONE 446-node cluster
#                          covering every sequencing tool; at 10 the same data
#                          resolves into 31 recognisable domains.
#   MIN_DIST/SPREAD        stop the core collapsing into an unreadable dot.
MIN_WORKFLOWS = int(os.environ.get("WFGAL_MIN_WORKFLOWS", 3))
SVD_DIMS = int(os.environ.get("WFGAL_SVD_DIMS", 100))
TEXT_WEIGHT = float(os.environ.get("WFGAL_TEXT_WEIGHT", 0.3))
N_NEIGHBORS = int(os.environ.get("WFGAL_N_NEIGHBORS", 10))
MIN_DIST = float(os.environ.get("WFGAL_MIN_DIST", 0.15))
SPREAD = float(os.environ.get("WFGAL_SPREAD", 1.3))


def ppmi(counts: np.ndarray) -> np.ndarray:
    """Positive pointwise mutual information over the tool x workflow matrix."""
    total = counts.sum()
    if total == 0:
        return counts
    row = counts.sum(axis=1, keepdims=True)
    col = counts.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        expected = (row @ col) / total
        m = np.log((counts * total) / np.where(expected == 0, 1e-12, expected) / total)
    m[~np.isfinite(m)] = 0.0
    return np.maximum(m, 0.0)


# Words that are frequent in tool descriptions but say nothing about domain.
# Without these the labels came out as "multiqc · sequencing, data, tool".
LABEL_STOP = [
    "data", "tool", "tools", "using", "use", "used", "uses", "file", "files",
    "based", "software", "program", "programs", "package", "suite", "library",
    "format", "formats", "input", "output", "outputs", "information", "various",
    "different", "set", "sets", "provides", "provide", "allows", "allow",
    "perform", "performs", "performing", "run", "runs", "running", "also",
    "can", "ext", "wrapper", "wrappers", "generic", "general", "simple", "fast",
    "new", "one", "two", "given", "user", "users", "step", "steps", "pipeline",
]


def ctfidf_labels(tools, labels, meta, cooc_names, top_n=4):
    """Label each cluster by its most distinctive terms (class-based TF-IDF)."""
    docs = collections.defaultdict(list)
    for t, lab in zip(tools, labels):
        if lab < 0:
            continue
        text = t.replace("_", " ") + " " + (meta.get(t, {}).get("description", ""))
        docs[lab].append(text)
    if not docs:
        return {}
    keys = sorted(docs)
    joined = [" ".join(docs[k]) for k in keys]
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    vec = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS) + LABEL_STOP,
                          max_features=6000,
                          token_pattern=r"[A-Za-z][A-Za-z0-9\-]{2,}")
    X = vec.fit_transform(joined)
    vocab = np.array(vec.get_feature_names_out())
    out = {}
    for i, k in enumerate(keys):
        row = X[i].toarray().ravel()
        top = vocab[np.argsort(-row)[:top_n]]
        # Prefer an actual high-degree tool name if one is in the cluster
        members = [t for t, lab in zip(tools, labels) if lab == k]
        hub = max(members, key=lambda t: cooc_names.get(t, 0)) if members else ""
        terms = [w for w in top if w.lower() != hub.lower()][:3]
        out[int(k)] = (hub + " · " + ", ".join(terms)).strip(" ·")
    return out


def main() -> None:
    corpus = json.load(open(os.path.join(WORK, "corpus.json"), encoding="utf-8"))
    wf_tools = {k: set(v) for k, v in corpus["wf_tools"].items()}
    wf_meta, meta = corpus["wf_meta"], corpus["meta"]

    freq = collections.Counter()
    for ts in wf_tools.values():
        freq.update(ts)
    tools = sorted(t for t, c in freq.items() if c >= MIN_WORKFLOWS)
    if len(tools) < 30:
        raise SystemExit(f"only {len(tools)} tools above threshold — corpus too small")
    tidx = {t: i for i, t in enumerate(tools)}
    wids = sorted(wf_tools)
    print(f"{len(tools)} tool nodes across {len(wids)} workflows")

    # --- co-usage side -----------------------------------------------------
    M = np.zeros((len(tools), len(wids)), dtype=np.float64)
    for j, w in enumerate(wids):
        for t in wf_tools[w]:
            if t in tidx:
                M[tidx[t], j] = 1.0
    P = ppmi(M)
    d1 = min(SVD_DIMS, min(P.shape) - 1)
    A = normalize(TruncatedSVD(n_components=d1, random_state=0).fit_transform(P))

    # --- description side --------------------------------------------------
    texts = [t.replace("_", " ") + " " + meta.get(t, {}).get("description", "")
             for t in tools]
    T = TfidfVectorizer(stop_words="english", min_df=2, max_features=20000,
                        token_pattern=r"[A-Za-z][A-Za-z0-9\-]{2,}").fit_transform(texts)
    d2 = min(SVD_DIMS, min(T.shape) - 1)
    B = normalize(TruncatedSVD(n_components=d2, random_state=0).fit_transform(T))

    X = np.hstack([A, B * TEXT_WEIGHT])
    print(f"feature matrix {X.shape}")

    # --- projection + clustering -------------------------------------------
    import umap
    # Domains like molecular dynamics share almost no tools with sequencing, so
    # the kNN graph fragments and UMAP throws those components a long way out,
    # leaving the main mass squeezed into a corner. A larger n_neighbors keeps
    # the graph connected; spread/min_dist stop the core collapsing to a dot.
    xy = umap.UMAP(n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST, spread=SPREAD,
                   metric="cosine", random_state=42).fit_transform(X)
    try:
        import hdbscan
        clusterer = hdbscan.HDBSCAN(min_cluster_size=max(5, len(tools) // 60),
                                    min_samples=3)
    except ImportError:
        # hdbscan needs MSVC build tools on Windows; scikit-learn >=1.3 ships a
        # compatible implementation, so the dependency is optional.
        from sklearn.cluster import HDBSCAN as SkHDBSCAN
        clusterer = SkHDBSCAN(min_cluster_size=max(5, len(tools) // 60),
                              min_samples=3)
    labels = clusterer.fit_predict(xy)
    print(f"clusters: {len(set(labels) - {-1})}, "
          f"unclustered: {int((labels == -1).sum())}")

    # --- per-node payload ---------------------------------------------------
    cooc = collections.Counter()
    pair = collections.Counter()
    for w, ts in wf_tools.items():
        sel = sorted(t for t in ts if t in tidx)
        for t in sel:
            cooc[t] += 1
        for a_i in range(len(sel)):
            for b_i in range(a_i + 1, len(sel)):
                pair[(sel[a_i], sel[b_i])] += 1

    neigh = collections.defaultdict(list)
    for (a, b), c in pair.items():
        neigh[a].append((c, b))
        neigh[b].append((c, a))

    tool_wfs = collections.defaultdict(list)
    for w, ts in wf_tools.items():
        for t in ts:
            if t in tidx:
                tool_wfs[t].append(w)

    # Which corpus does each tool come from? Drives the colour-by-source view;
    # a tool used in both nf-core and DH notebooks is genuinely interesting.
    SRC_FAMILY = {"nf-core": "nf-core", "galaxy-iwc": "galaxy",
                  "galaxy-training": "galaxy", "workflowhub": "workflowhub",
                  "dockstore": "dockstore", "dh-notebooks": "dh"}
    tool_src = collections.defaultdict(collections.Counter)
    for w, ts in wf_tools.items():
        fam = SRC_FAMILY.get(wf_meta[w]["src"], "other")
        for t in ts:
            if t in tidx:
                tool_src[t][fam] += 1

    labs = ctfidf_labels(tools, labels, meta, cooc)

    xy = np.asarray(xy, dtype=float)
    nodes = []
    for i, t in enumerate(tools):
        m = meta.get(t, {})
        # Edge candidates: strongest co-occurrences, with the count kept so the
        # map can weight the lines it draws.
        top_pairs = sorted(neigh[t], reverse=True)[:8]
        nodes.append({
            "id": t,
            "label": m.get("name") or t,
            "x": round(float(xy[i, 0]), 3),
            "y": round(float(xy[i, 1]), 3),
            "n": int(freq[t]),
            "c": int(labels[i]),
            "desc": m.get("description", ""),
            "url": m.get("homepage", ""),
            "doi": m.get("doi", ""),
            "lic": m.get("licence", ""),
            "top": [b for _, b in top_pairs],
            "tw": [int(c) for c, _ in top_pairs],
            "src": tool_src[t].most_common(1)[0][0] if tool_src[t] else "other",
            "srcs": dict(tool_src[t]),
            "wfs": [{"n": wf_meta[w]["name"], "u": wf_meta[w].get("url", ""),
                     "s": wf_meta[w]["src"]}
                    for w in sorted(tool_wfs[t])[:25]],
        })

    centroids = []
    for c in sorted(set(labels) - {-1}):
        pts = xy[labels == c]
        centroids.append({
            "c": int(c),
            "x": round(float(pts[:, 0].mean()), 3),
            "y": round(float(pts[:, 1].mean()), 3),
            "n": int((labels == c).sum()),
            "label": labs.get(int(c), f"cluster {c}"),
        })

    n_doi = sum(1 for n in nodes if n["doi"])
    n_desc = sum(1 for n in nodes if n["desc"])
    print(f"nodes with a description: {n_desc}/{len(nodes)}  with a DOI: {n_doi}")
    print("by source:", dict(collections.Counter(n["src"] for n in nodes)))

    out = {"nodes": nodes, "clusters": centroids,
           "stats": {"workflows": len(wids), "tools": len(tools),
                     "with_doi": n_doi, "with_desc": n_desc,
                     "params": {"min_workflows": MIN_WORKFLOWS,
                                "text_weight": TEXT_WEIGHT,
                                "n_neighbors": N_NEIGHBORS},
                     "sources": sorted({m["src"] for m in wf_meta.values()})}}
    json.dump(out, open(os.path.join(WORK, "layout.json"), "w"))
    print(f"-> {os.path.join(WORK, 'layout.json')}")


if __name__ == "__main__":
    main()
