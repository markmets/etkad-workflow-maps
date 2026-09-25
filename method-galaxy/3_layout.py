#!/usr/bin/env python3
"""Stage 3: lay out two spaces, several ways each.

TWO SPACES
  method space  147 TaDiRAH activities. Small enough to label every node — this
                is "the map of DH methods as actually practised".
  item  space   ~2,400 Marketplace objects + ETKAD's workflows, placed by which
                methods they share. This is the galaxy ETKAD gets plotted into.

SEVERAL METRICS, shipped together so the map can switch between them live.
Different metrics disagree in instructive ways: PPMI+cosine asks "do these
co-occur more than chance?", raw cosine asks "do these co-occur a lot?" (so
ubiquitous methods drift to the centre), and Jaccard asks "how much do their
item sets overlap?" regardless of size.

Also computed here, because the browser should not have to:
  - c-TF-IDF cluster labels
  - each ETKAD workflow's nearest Marketplace items (the recommender)
  - each ETKAD workflow's stage path through method space (the constellation)
  - a gap score per method: common in Europe, unused in Estonia

Output: work/layout.json
"""
import collections
import json
import os

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.preprocessing import normalize

WORK = os.path.abspath(os.environ.get("MGAL_WORK", "./work"))
SVD_DIMS = int(os.environ.get("MGAL_SVD_DIMS", 80))
SEED = 42

LABEL_STOP = ["data", "tool", "tools", "using", "use", "used", "analysis",
              "based", "software", "digital", "research", "online", "web",
              "http", "https", "www", "com", "org", "project", "resource",
              "resources", "information", "provides", "available", "new"]


def ppmi(counts):
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


def jaccard_embed(M, dims):
    """Embed rows by Jaccard similarity to every other row.

    Jaccard ignores how often a thing is used and asks only how much two things'
    item sets overlap, which keeps rare-but-specific methods from being crushed
    by ubiquitous ones like `Analyzing`.
    """
    B = (M > 0).astype(np.float64)
    inter = B @ B.T
    sizes = B.sum(axis=1, keepdims=True)
    union = sizes + sizes.T - inter
    J = inter / np.where(union == 0, 1, union)
    d = min(dims, min(J.shape) - 1)
    return normalize(TruncatedSVD(n_components=max(2, d), random_state=SEED)
                     .fit_transform(J))


def embed(M, mode, dims):
    if mode == "jaccard":
        return jaccard_embed(M, dims)
    X = ppmi(M) if mode == "ppmi" else M.astype(np.float64)
    d = min(dims, min(X.shape) - 1)
    return normalize(TruncatedSVD(n_components=max(2, d), random_state=SEED)
                     .fit_transform(X))


def project(X, n_neighbors, min_dist=0.2, spread=1.4):
    import umap
    return umap.UMAP(n_neighbors=min(n_neighbors, max(2, X.shape[0] - 1)),
                     min_dist=min_dist, spread=spread, metric="cosine",
                     random_state=SEED).fit_transform(X)


def cluster(xy, min_size):
    try:
        import hdbscan
        c = hdbscan.HDBSCAN(min_cluster_size=min_size, min_samples=2)
    except ImportError:
        from sklearn.cluster import HDBSCAN as SkH
        c = SkH(min_cluster_size=min_size, min_samples=2)
    return c.fit_predict(np.asarray(xy, dtype=float))


def ctfidf(names, texts, labels, weight, top_n=3):
    docs = collections.defaultdict(list)
    for nm, tx, lab in zip(names, texts, labels):
        if lab >= 0:
            docs[lab].append(nm + " " + tx)
    if not docs:
        return {}
    keys = sorted(docs)
    vec = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS) + LABEL_STOP,
                          max_features=8000,
                          token_pattern=r"[A-Za-z][A-Za-z0-9\-]{2,}")
    X = vec.fit_transform([" ".join(docs[k]) for k in keys])
    vocab = np.array(vec.get_feature_names_out())
    out = {}
    for i, k in enumerate(keys):
        row = X[i].toarray().ravel()
        top = [w for w in vocab[np.argsort(-row)[:top_n + 2]]]
        members = [n for n, l in zip(names, labels) if l == k]
        hub = max(members, key=lambda n: weight.get(n, 0)) if members else ""
        terms = [w for w in top if w.lower() not in hub.lower()][:top_n]
        out[int(k)] = (hub + " · " + ", ".join(terms)).strip(" ·")
    return out


def scatter_layouts(M, names, texts, weight, neighbors, min_size, modes):
    """One UMAP + clustering per distance mode, all keyed by mode name."""
    out = {}
    for mode in modes:
        X = embed(M, mode, SVD_DIMS)
        xy = np.asarray(project(X, neighbors), dtype=float)
        lab = cluster(xy, min_size)
        labs = ctfidf(names, texts, lab, weight)
        out[mode] = {
            "xy": [[round(float(a), 3), round(float(b), 3)] for a, b in xy],
            "c": [int(x) for x in lab],
            "clusters": [{"c": int(c),
                          "x": round(float(xy[lab == c][:, 0].mean()), 3),
                          "y": round(float(xy[lab == c][:, 1].mean()), 3),
                          "n": int((lab == c).sum()),
                          "label": labs.get(int(c), f"cluster {c}")}
                         for c in sorted(set(lab) - {-1})],
        }
        print(f"    {mode:8} -> {len(out[mode]['clusters']):2} clusters, "
              f"{int((lab == -1).sum()):4} unclustered")
    return out


def main():
    corpus = json.load(open(os.path.join(WORK, "corpus.json"), encoding="utf-8"))
    items, acts, etkad_ids = corpus["items"], corpus["activities"], corpus["etkad"]

    act_names = sorted(acts)
    aidx = {a: i for i, a in enumerate(act_names)}
    item_ids = sorted(items)
    iidx = {k: i for i, k in enumerate(item_ids)}

    # incidence: activity x item
    A = np.zeros((len(act_names), len(item_ids)), dtype=np.float64)
    for k, v in items.items():
        for a in v["acts"]:
            if a in aidx:
                A[aidx[a], iidx[k]] = 1.0
    print(f"incidence {A.shape} — {len(act_names)} activities x {len(item_ids)} items")

    MODES = ["ppmi", "jaccard", "raw"]

    # ---------------- method space ----------------
    print("\nmethod space (activities):")
    a_weight = {a: acts[a]["n"] for a in act_names}
    # Label text from Marketplace items only. Including the ETKAD titles put
    # fragments of Estonian words ("kasutusv", "imaluse") into cluster labels —
    # ten documents out of 2,376 dominated c-TF-IDF because their vocabulary
    # appears nowhere else in the corpus.
    a_text = [" ".join(w["label"] for w in items.values()
                       if w["origin"] == "sshomp" and a in w["acts"])[:4000]
              for a in act_names]
    method_layouts = scatter_layouts(A, act_names, a_text, a_weight,
                                     neighbors=10, min_size=4, modes=MODES)

    # ---------------- item space ----------------
    print("\nitem space (Marketplace objects + ETKAD workflows):")
    # Label the item clusters with readable titles. Passing persistent IDs here
    # produced cluster captions like "shomp:2FIJCW · heritage, cultural" —
    # the hub is chosen from this list, so it has to be human-readable.
    i_names = [items[k]["label"][:60] for k in item_ids]
    i_weight = {}
    for k, nm in zip(item_ids, i_names):
        i_weight[nm] = max(i_weight.get(nm, 0), len(items[k]["acts"]))
    i_text = [(items[k]["desc"] or "") + " " + " ".join(items[k]["kw"][:8])
              for k in item_ids]
    item_layouts = scatter_layouts(A.T, i_names, i_text, i_weight,
                                   neighbors=15, min_size=20, modes=MODES)

    # ---------------- co-occurrence, per activity ----------------
    co = collections.Counter()
    for v in items.values():
        s = sorted(set(v["acts"]))
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                co[(s[i], s[j])] += 1
    neigh = collections.defaultdict(list)
    for (x, y), c in co.items():
        neigh[x].append((c, y))
        neigh[y].append((c, x))

    examples = collections.defaultdict(list)
    for k, v in items.items():
        for a in v["acts"]:
            if len(examples[a]) < 12:
                examples[a].append({"id": k, "n": v["label"][:70],
                                    "c": v["cat"], "u": v["url"]})

    total_items = len(items)
    n_etkad = max(1, len(etkad_ids))
    ee_used = {a for a in act_names if acts[a]["etkad"] > 0}

    method_nodes = []
    for a in act_names:
        top = sorted(neigh[a], reverse=True)[:8]
        share_eu = acts[a]["n"] / total_items
        share_ee = acts[a]["etkad"] / n_etkad
        # "Adjacent opportunity": for a method Estonia does NOT use, how strongly
        # is it tied to the methods Estonia DOES use? A high score means European
        # practice routinely pairs it with things already being done here, so it
        # is a plausible next step rather than an unrelated speciality. This is
        # far more actionable than raw "most popular unused method".
        adj = 0.0
        if a not in ee_used and acts[a]["n"]:
            shared = sum(c for c, other in neigh[a] if other in ee_used)
            adj = shared / acts[a]["n"]
        method_nodes.append({
            "id": a, "n": acts[a]["n"], "etkad": acts[a]["etkad"],
            "group": acts[a]["group"], "et": acts[a].get("et", ""),
            # >0 means Europe uses it more than Estonia does; the gap finder.
            "gap": round(share_eu - share_ee, 4),
            "adj": round(adj, 3),
            "top": [y for _, y in top], "tw": [int(c) for c, _ in top],
            "ex": examples[a],
        })

    # ---------------- ETKAD extras ----------------
    # nearest Marketplace items to each ETKAD workflow, by Jaccard over methods
    B = (A.T > 0).astype(np.float64)
    inter = B @ B.T
    sizes = B.sum(axis=1, keepdims=True)
    union = sizes + sizes.T - inter
    J = inter / np.where(union == 0, 1, union)
    etkad_set = set(etkad_ids)
    recs = {}
    for wid in etkad_ids:
        r = J[iidx[wid]]
        order = np.argsort(-r)
        out = []
        for j in order:
            k = item_ids[j]
            if k == wid or k in etkad_set or r[j] <= 0:
                continue
            out.append({"id": k, "n": items[k]["label"][:80], "c": items[k]["cat"],
                        "u": items[k]["url"], "s": round(float(r[j]), 3),
                        "shared": sorted(set(items[k]["acts"]) & set(items[wid]["acts"]))[:6]})
            if len(out) >= 12:
                break
        recs[wid] = out

    # ---------------- workflow shape (experimental) ----------------
    # ETKAD tags methods PER STAGE, in order. Nothing else in this corpus does,
    # so this is the one question only the Estonian data can answer: where in a
    # workflow does each kind of method actually happen? Position is normalised
    # to 0..1 across a workflow's stages so a 4-stage and an 11-stage workflow
    # are comparable.
    grp_of = {n["id"]: n["group"] for n in method_nodes}
    pos = collections.defaultdict(list)
    gpos = collections.defaultdict(list)
    transitions = collections.Counter()
    for wid in etkad_ids:
        stages = items[wid].get("stages", [])
        if len(stages) < 2:
            continue
        denom = len(stages) - 1
        prev_groups = set()
        for si, st in enumerate(stages):
            t = si / denom
            groups_here = set()
            for a in st["acts"]:
                pos[a].append(t)
                g = grp_of.get(a, "Other")
                gpos[g].append(t)
                groups_here.add(g)
            for pg in prev_groups:
                for g in groups_here:
                    if pg != g:
                        transitions[(pg, g)] += 1
            prev_groups = groups_here

    shape = {
        "groups": sorted(
            ({"g": g, "mean": round(sum(v) / len(v), 3), "n": len(v),
              "lo": round(min(v), 3), "hi": round(max(v), 3)}
             for g, v in gpos.items()), key=lambda d: d["mean"]),
        "methods": sorted(
            ({"id": a, "mean": round(sum(v) / len(v), 3), "n": len(v),
              "group": grp_of.get(a, "Other")}
             for a, v in pos.items() if len(v) >= 2), key=lambda d: d["mean"]),
        "transitions": sorted(
            ({"from": a, "to": b, "n": c} for (a, b), c in transitions.items()),
            key=lambda d: -d["n"])[:24],
        "n_workflows": sum(1 for w in etkad_ids if len(items[w].get("stages", [])) >= 2),
    }
    print(f"\nworkflow shape: {len(shape['groups'])} goals positioned across "
          f"{shape['n_workflows']} staged workflows, "
          f"{len(shape['transitions'])} goal transitions")

    item_nodes = []
    for k in item_ids:
        v = items[k]
        item_nodes.append({
            "id": k, "label": v["label"][:110], "cat": v["cat"],
            "acts": v["acts"], "desc": (v["desc"] or "")[:420], "url": v["url"],
            "src": v.get("src", ""), "kw": v.get("kw", [])[:10],
            "langs": v.get("langs", [])[:4], "origin": v["origin"],
            "na": len(v["acts"]),
            **({"stages": v.get("stages", []), "et": v.get("et_terms", []),
                "disc": v.get("disciplines", []), "out": v.get("output", []),
                "media": v.get("media", []), "lic": v.get("licence", ""),
                "authors": v.get("authors", []), "recs": recs.get(k, []),
                "named": v.get("named_tools", [])}
               if v["origin"] == "etkad" else {}),
        })

    payload = {
        "method": {"nodes": method_nodes, "layouts": method_layouts},
        "item": {"nodes": item_nodes, "layouts": item_layouts},
        "etkad": etkad_ids,
        "shape": shape,
        "modes": MODES,
        # Defaults chosen by comparing the clusterings. On 147 activities PPMI
        # over-smooths into 2 giant clusters; raw co-occurrence resolves them
        # into recognisable families (OCR/recognition, capture, discovery,
        # identifiers, curation). The item space is the opposite: it is large
        # and dominated by ubiquitous methods, so PPMI is what gives it shape.
        "default_mode": {"method": "raw", "item": "ppmi"},
        "stats": {
            "items": len(items), "sshomp": len(items) - len(etkad_ids),
            "etkad": len(etkad_ids), "activities": len(act_names),
            "etkad_activities": sum(1 for a in act_names if acts[a]["etkad"]),
            "cats": dict(collections.Counter(v["cat"] for v in items.values())),
        },
    }
    json.dump(payload, open(os.path.join(WORK, "layout.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    mb = os.path.getsize(os.path.join(WORK, "layout.json")) / 1e6
    print(f"\n-> work/layout.json ({mb:.1f} MB)")
    print(f"   methods {len(method_nodes)}, items {len(item_nodes)}, "
          f"{len(MODES)} metrics x 2 spaces = {2*len(MODES)} layouts")


if __name__ == "__main__":
    main()
