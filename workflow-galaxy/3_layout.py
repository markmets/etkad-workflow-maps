#!/usr/bin/env python3
"""Stage 3: one layout per facet, plus everything the browser should not compute.

The corpus is only 237 workflows, which is small enough to change the
architecture: instead of shipping fixed coordinates and hoping the user wants
the map we built, we ship the *feature vectors* and let the browser recompute
similarity live as the facet weights move. 237 x 237 cosine over sparse vectors
is a few milliseconds of JavaScript.

Positions still need a real embedding, so a UMAP per facet is precomputed here
and the browser snaps to whichever one matches the current weighting; a custom
blend falls back to client-side stress majorisation on the blended distances.

Also computed here:
  * clusters and c-TF-IDF labels per facet
  * the goal transition graph, aggregated over every workflow that has ordered
    method tags — the "what follows what" structure
  * the average shape of a workflow, by source
  * a held-out evaluation: hide a fifth of each workflow's methods, ask the
    remaining facets to predict them, and report how often they do. This is the
    only thing here that can say whether the map is any good rather than merely
    pretty.

Output: work/atlas.json
"""
import collections
import json
import math
import os
import random
import sys

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.preprocessing import normalize

WORK = os.path.abspath(os.environ.get("WFA_WORK", "./work"))
SEED = 42
FACETS = ["method", "goal", "tool", "topic", "material", "flow", "text"]
# Facets that are sparse or coarse pull the blend around too much at equal
# weight, so the default emphasises the two that nearly every workflow has and
# that carry the most distinct signal.
DEFAULT_W = {"method": 1.0, "goal": 0.3, "tool": 0.8, "topic": 0.6,
             "material": 0.2, "flow": 0.4, "text": 0.5}

LABEL_STOP = ["data", "tool", "tools", "using", "use", "used", "analysis",
              "based", "software", "digital", "research", "online", "web",
              "http", "https", "www", "com", "org", "project", "workflow",
              "lesson", "resource", "resources", "information", "new", "step"]


def idf_weights(rows, vocab):
    n = len(rows) or 1
    df = collections.Counter(f for r in rows for f in set(r))
    return np.array([math.log(1 + n / (1 + df.get(v, 0))) for v in vocab])


def facet_matrix(recs, facet):
    """Binary incidence weighted by idf, L2-normalised. Cosine on this is the
    similarity the browser reproduces."""
    vocab = sorted({f for r in recs for f in r["facets"][facet]})
    ix = {v: i for i, v in enumerate(vocab)}
    M = np.zeros((len(recs), len(vocab)), dtype=np.float64)
    for i, r in enumerate(recs):
        for f in r["facets"][facet]:
            M[i, ix[f]] = 1.0
    if not vocab:
        return vocab, M, np.zeros(0)
    w = idf_weights([r["facets"][facet] for r in recs], vocab)
    M = M * w
    return vocab, normalize(M), w


def project(X, n_neighbors=8, min_dist=0.18, spread=1.3):
    import umap
    n = X.shape[0]
    return umap.UMAP(n_neighbors=min(n_neighbors, max(2, n - 1)),
                     min_dist=min_dist, spread=spread, metric="cosine",
                     random_state=SEED).fit_transform(X)


def cluster(xy, min_size=6):
    try:
        import hdbscan
        c = hdbscan.HDBSCAN(min_cluster_size=min_size, min_samples=2)
    except ImportError:
        from sklearn.cluster import HDBSCAN as SkH
        c = SkH(min_cluster_size=min_size, min_samples=2)
    return c.fit_predict(np.asarray(xy, dtype=float))


def ctfidf(titles, texts, labels, top_n=3):
    docs = collections.defaultdict(list)
    for t, x, l in zip(titles, texts, labels):
        if l >= 0:
            docs[l].append(t + " " + x)
    if not docs:
        return {}
    keys = sorted(docs)
    vec = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS) + LABEL_STOP,
                          max_features=6000,
                          token_pattern=r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\-]{2,}")
    X = vec.fit_transform([" ".join(docs[k]) for k in keys])
    vocab = np.array(vec.get_feature_names_out())
    return {int(k): ", ".join(vocab[np.argsort(-X[i].toarray().ravel())[:top_n]])
            for i, k in enumerate(keys)}


def layout_for(recs, M, titles, texts, tag):
    if M.shape[1] < 2 or not M.any():
        return None
    d = min(60, min(M.shape) - 1)
    X = normalize(TruncatedSVD(n_components=max(2, d), random_state=SEED)
                  .fit_transform(M)) if M.shape[1] > 60 else M
    xy = np.asarray(project(X), dtype=float)
    lab = cluster(xy)
    labs = ctfidf(titles, texts, lab)
    ncl = len(set(int(x) for x in lab if x >= 0))
    print(f"  {tag:9} {M.shape[1]:5} features -> {ncl:2} clusters, "
          f"{int((lab == -1).sum()):3} unclustered")
    return {"xy": [[round(float(a), 3), round(float(b), 3)] for a, b in xy],
            "c": [int(x) for x in lab],
            "labels": {str(k): v for k, v in labs.items()}}


# --------------------------------------------------------------------------
# transition graph
# --------------------------------------------------------------------------
def transitions(recs, goal_of):
    """What follows what, at goal level, across every ordered tagged workflow.

    Only ETKAD and half the Marketplace workflows tag per step, so this rests on
    ~50 workflows — enough to see structure, not enough to be authoritative, and
    the map says so.
    """
    edges, nodes, contributors = collections.Counter(), collections.Counter(), set()
    for r in recs:
        seq = [sorted({goal_of.get(m, "") for m in s["methods"]} - {""})
               for s in r["steps"]]
        seq = [g for g in seq if g]
        if len(seq) < 2:
            continue
        contributors.add(r["id"])
        for g in seq:
            nodes.update(g)
        for a, b in zip(seq, seq[1:]):
            for x in a:
                for y in b:
                    edges[(x, y)] += 1
    return ({"edges": [{"a": a, "b": b, "n": n} for (a, b), n in edges.most_common()],
             "nodes": dict(nodes), "from": len(contributors)})


def shape_profile(recs, goal_of):
    """Where in a run each goal happens, normalised to 0..1 and averaged."""
    pos = collections.defaultdict(list)
    per_src = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in recs:
        tagged = [(s["n"], {goal_of.get(m, "") for m in s["methods"]} - {""})
                  for s in r["steps"]]
        tagged = [(n, g) for n, g in tagged if g]
        if len(tagged) < 3:
            continue
        last = max(n for n, _ in tagged) or 1
        for n, goals in tagged:
            for g in goals:
                pos[g].append(n / last)
                per_src[r["src"]][g].append(n / last)
    out = {g: {"mean": round(float(np.mean(v)), 3), "n": len(v)}
           for g, v in pos.items()}
    bysrc = {s: {g: round(float(np.mean(v)), 3) for g, v in d.items() if len(v) >= 3}
             for s, d in per_src.items()}
    return {"all": out, "by_source": bysrc}


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def evaluate(recs, mats, k=5, folds=5):
    """Hide a fifth of a workflow's methods; can its neighbours guess them?

    For each facet in turn we rank neighbours by that facet alone, pool the
    methods of the top k, and ask whether the held-out methods appear. Facets
    that beat the popularity baseline are carrying real information about what a
    workflow does; ones that do not are decoration.
    """
    rng = random.Random(SEED)
    have = [i for i, r in enumerate(recs) if len(r["methods"]) >= 4]
    if len(have) < 20:
        return {}
    pop = collections.Counter(m for r in recs for m in r["methods"])
    top_pop = [m for m, _ in pop.most_common(12)]

    results = {}
    for facet, (_, M, _) in mats.items():
        if M.shape[1] < 2 or not M.any():
            continue
        S = M @ M.T
        np.fill_diagonal(S, -1)
        hit = tot = 0
        for i in have:
            ms = list(recs[i]["methods"])
            rng.shuffle(ms)
            cut = max(1, len(ms) // 5)
            held, kept = set(ms[:cut]), set(ms[cut:])
            nbrs = np.argsort(-S[i])[:k]
            pred = set()
            for j in nbrs:
                pred |= set(recs[j]["methods"])
            pred -= kept
            hit += len(held & pred)
            tot += len(held)
        results[facet] = round(100 * hit / max(1, tot), 1)
    # baseline: always answer with the most common methods
    hit = tot = 0
    for i in have:
        ms = list(recs[i]["methods"])
        rng.shuffle(ms)
        cut = max(1, len(ms) // 5)
        held, kept = set(ms[:cut]), set(ms[cut:])
        pred = set(top_pop) - kept
        hit += len(held & pred)
        tot += len(held)
    results["_popularity_baseline"] = round(100 * hit / max(1, tot), 1)
    results["_n"] = len(have)
    results["_k"] = k
    return results


def main():
    corpus = json.load(open(os.path.join(WORK, "corpus.json"), encoding="utf-8"))
    recs, goal_of = corpus["workflows"], corpus["goal_of"]
    titles = [r["title"] for r in recs]
    texts = [" ".join(r["facets"]["topic"] + r["facets"]["text"][:15]) for r in recs]

    print(f"{len(recs)} workflows\n\nlayouts")
    mats, layouts, vecs = {}, {}, {}
    for f in FACETS:
        vocab, M, w = facet_matrix(recs, f)
        mats[f] = (vocab, M, w)
        lay = layout_for(recs, M, titles, texts, f)
        if lay:
            layouts[f] = lay
        # sparse form for the browser: [index, weight] per workflow
        ix = {v: i for i, v in enumerate(vocab)}
        vecs[f] = {"vocab": vocab,
                   "rows": [[[ix[x], round(float(w[ix[x]]), 4)]
                             for x in r["facets"][f]] for r in recs]}

    # blended layout at the default weights
    blend = np.hstack([mats[f][1] * DEFAULT_W[f] for f in FACETS
                       if mats[f][1].shape[1] >= 2])
    blend = normalize(blend)
    lay = layout_for(recs, blend, titles, texts, "blend")
    if lay:
        layouts["blend"] = lay

    print("\nheld-out method prediction (top-5 neighbours, % of hidden methods recovered)")
    ev = evaluate(recs, mats)
    for k, v in sorted(ev.items(), key=lambda kv: -kv[1] if isinstance(kv[1], float) else 0):
        if not k.startswith("_"):
            print(f"  {k:9} {v:5.1f}%")
    print(f"  {'popularity':9} {ev.get('_popularity_baseline', 0):5.1f}%  "
          f"(baseline, n={ev.get('_n')})")

    tr = transitions(recs, goal_of)
    sh = shape_profile(recs, goal_of)
    print(f"\ntransition graph: {len(tr['edges'])} goal edges from "
          f"{tr['from']} ordered workflows")
    print("shape (mean normalised position):")
    for g, d in sorted(sh["all"].items(), key=lambda kv: kv[1]["mean"]):
        print(f"  {g:15} {d['mean']:.2f}  ({d['n']} taggings)")

    out = {
        "workflows": [{k: r[k] for k in
                       ("id", "src", "title", "desc", "url", "lang", "methods",
                        "goals", "tools", "topics", "materials", "steps",
                        "method_src", "nsteps", "ntagged", "licence")}
                      for r in recs],
        "facets": FACETS, "default_w": DEFAULT_W,
        "vectors": vecs, "layouts": layouts,
        "eval": ev, "transitions": tr, "shape": sh,
        "goal_order": corpus["goal_order"], "goal_of": goal_of,
    }
    p = os.path.join(WORK, "atlas.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\n-> {p}  ({os.path.getsize(p)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
