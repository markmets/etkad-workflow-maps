#!/usr/bin/env python3
"""Stage 2: fold three sources into one workflow record with comparable facets.

THE POINT OF THE FACETS
-----------------------
"Similar workflows" is not one question. Two workflows can be alike because they
use the same methods, because they use the same software, because they work on
the same material, because they are about the same subject, or because they have
the same shape — the same order of operations regardless of topic. Those give
genuinely different neighbours, so the map lets you choose which one you mean.

  method    TaDiRAH activities                     declared (MP, ETKAD) / inferred (PH)
  goal      the 8 TaDiRAH goal groups              coarser view of the same thing
  tool      named software                         gazetteer match against 1,892 MP tools
  topic     keywords, disciplines, EMS subjects    what it is about
  material  input/output formats, media types      what it is done to
  flow      ordered goal bigrams + position bins   the shape, not the content
  text      TF-IDF terms of title/abstract/steps   the wording

Each facet is a bag of feature strings. Stage 3 turns them into vectors; the
browser recombines them live with weights, which is what makes "choose the
aspect" a real control and not a menu of prebaked maps.

WHAT IS DECLARED AND WHAT IS INFERRED
-------------------------------------
Marketplace and ETKAD workflows carry TaDiRAH tags applied by a human. PH lessons
carry none, so their methods are matched out of the prose. That difference is
recorded per workflow (`method_src`) and shown in the map, because a comparison
between a declared tag and an inferred one is weaker evidence than between two
declared ones, and the map should not hide that.

Output: work/corpus.json
"""
import collections
import json
import os
import re
import sys

from vocab import ET2EN, GROUPS, KNOWN_UNMAPPED

WORK = os.path.abspath(os.environ.get("WFA_WORK", "./work"))
RAW = os.path.join(WORK, "raw")

GOAL_OF = {m: g for g, ms in GROUPS.items() for m in ms}
# Conceptual order of the goals; used for the flow facet and the shape view.
GOAL_ORDER = ["Capture", "Discovery", "Enrichment", "Storage", "Analysis",
              "Interpretation", "Creation", "Dissemination"]

# PH's own five-verb activity vocabulary, mapped onto TaDiRAH goals.
PH_ACT2GOAL = {"acquiring": "Capture", "transforming": "Enrichment",
               "analyzing": "Analysis", "presenting": "Dissemination",
               "sustaining": "Storage"}

# Activity labels too generic to match safely in free prose. Every one of these
# is an ordinary English word that appears in tutorials for reasons unrelated to
# the method: "adding a column", "sharing your results", "a description of".
UNSAFE_MATCH = {
    "adding", "improving", "sharing", "upload", "recording", "description",
    "defining", "associate", "associating", "identifier", "migration",
    "merging", "modifying", "finding", "comparing", "mapping", "managing",
    "creating", "writing", "editing", "formatting", "correcting", "cleaning",
    "integrating", "converting", "storing", "posting", "gathering", "teaching",
    "discussing", "searching", "browsing", "exploration", "identifying",
    "collecting", "capturing", "analyzing", "modeling", "programming",
    "designing", "organizing", "highlighting", "segmenting", "encoding",
    "extracting", "enriching", "annotating", "tagging", "translating",
    "transcribing", "scanning", "imaging", "querying", "publishing",
    "interpreting", "archiving", "preserving", "cataloging", "aggregating",
    "replication", "compiling", "collating", "cropping", "debugging",
    "abstract thinking", "co-occurrence", "transformation", "plotting",
}

# Words that are real Marketplace tool names and also ordinary words. `Ning` is a
# social platform and the Estonian for "and"; `Voyant` is safe, `Ant` is not.
TOOL_MATCH_STOP = {
    "ning", "data", "text", "image", "images", "corpus", "corpora", "archive",
    "atlas", "notebook", "notebooks", "network", "networks", "graph", "graphs",
    "table", "tables", "media", "sound", "audio", "video", "photo", "photos",
    "story", "stories", "history", "museum", "library", "libraries", "index",
    "reader", "writer", "editor", "viewer", "browser", "server", "cloud",
    "portal", "search", "browse", "collection", "collections", "catalogue",
    "catalog", "project", "projects", "science", "sciences", "research",
    "digital", "online", "open", "openness", "european", "europe", "english",
    "french", "german", "italian", "spanish", "dutch", "polish", "greek",
    "chart", "charts", "colour", "color", "cases", "case", "trends", "trend",
    "context", "contexts", "author", "authors", "source", "sources", "word",
    "words", "language", "languages", "linguistics", "manuscript", "letters",
    "time", "times", "place", "places", "space", "spaces", "vision", "voice",
    # Real Marketplace tool names that are also ordinary words. Case-sensitive
    # matching kills most of these, but they still fire at the start of a
    # sentence or in a heading, so they are excluded outright.
    "topic", "topics", "topic modeling", "topic modelling", "things", "origin",
    "icon", "icons", "pattern", "patterns", "concordance", "hypotheses",
    "annotations", "annotation", "spatial", "sentiment", "similarity",
    "excel", "keywords", "metadata", "citation", "citations", "transcription",
    "visualisation", "visualization", "classification", "recognition",
    "processing", "papers", "colaboratory", "gazetteer", "dictionary",
    "encyclopedia", "timeline", "concordancer", "compare", "explore",
}

# Names that cannot be mistaken for an ordinary word: a digit, an internal
# capital, or punctuation inside the name.
DISTINCTIVE = re.compile(r"[0-9]|(?<=.)[A-Z]|[._/+-]")

STOP_TEXT = set("""a an the and or of to in for with on at by from as is are was were be been
this that these those it its into their there here we you your our can will may
about between over under more most other some such only own same than then once
using use used uses how what which who when where why not no nor but if because
while during before after above below up down out off again further both each
few many much very s t don should now also one two three first second new like
lesson tutorial section chapter step steps example examples""".split())


def load(tag):
    p = os.path.join(RAW, tag + ".json")
    if not os.path.exists(p):
        sys.exit(f"missing {p} — run 1_harvest.py first")
    return json.load(open(p, encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def goal_of(m):
    return GOAL_OF.get(m, "")


# --------------------------------------------------------------------------
# gazetteers built from the 6,305-item corpus
# --------------------------------------------------------------------------
def build_gazetteers(items):
    """Tool names to look for in prose, and the canonical activity label set."""
    tools = []
    for it in items:
        if it["cat"] not in ("tool-or-service",):
            continue
        nm = norm(it["label"])
        # Split only on separators followed by prose, never a bare hyphen, so
        # hyphenated names such as READ-IT survive intact.
        head = re.split(r":| – | — | - |\(|,", nm)[0].strip()
        if len(head) < 4 or head.lower() in TOOL_MATCH_STOP:
            continue
        tools.append((head, nm, it["id"]))
    # longest first so "Voyant Tools" wins over "Voyant"
    tools.sort(key=lambda t: -len(t[0]))
    acts = sorted({a for it in items for a in it["acts"]})
    return tools, acts


def match_tools(text, tools, cap=25):
    """Marketplace tools whose name literally appears in a workflow's prose.

    Matching is CASE-SENSITIVE against the tool's own capitalisation. Tool names
    are proper nouns, so `Voyant`, `AntConc` and `OpenRefine` are unaffected,
    while lowercase names like `word2vec` and `spaCy` still match themselves.
    Case-insensitive matching produced a long tail of nonsense: the Marketplace
    contains tools genuinely called Topic, Things, Origin, Icon, Pattern and
    Concordance, and every one of them fired on ordinary prose.
    """
    body = " " + re.sub(r"\s+", " ", text) + " "
    hits, seen = [], set()
    for head, full, pid in tools:
        # Dedupe case-insensitively: the Marketplace holds both `AntConc` and
        # `Antconc` as separate records, and listing both helps nobody.
        if head.lower() in seen:
            continue
        # A name is distinctive if it could not be mistaken for a plain word:
        # it carries a digit, internal capitals or punctuation. Those match
        # case-insensitively, so `Word2Vec` still finds `word2vec` in the prose.
        # Everything else must match its own capitalisation exactly.
        flags = re.I if DISTINCTIVE.search(head) else 0
        if re.search(r"(?<![\w])" + re.escape(head) + r"(?![\w])", body, flags):
            seen.add(head.lower())
            hits.append({"name": full, "id": pid})
            if len(hits) >= cap:
                break
    return hits


def match_methods(text, acts):
    """TaDiRAH activities named in prose. Multiword labels are matched whole;
    single-word labels only when they are not ordinary English."""
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    out = []
    for a in acts:
        al = a.lower()
        if al in UNSAFE_MATCH:
            continue
        if len(al) < 5 and " " not in al:
            continue
        if re.search(r"(?<![\w])" + re.escape(al) + r"(?![\w])", low):
            out.append(a)
    return out


def drop_ubiquitous(records, key, ratio=0.5):
    """A feature that fires in half a heterogeneous corpus is matching an
    ordinary word, not a thing. Cheap, corpus-driven, and catches collisions no
    hand-written stoplist anticipates."""
    n = len(records) or 1
    c = collections.Counter(f for r in records for f in set(r[key]))
    banned = {f for f, k in c.items() if k / n >= ratio}
    for r in records:
        r[key] = [f for f in r[key] if f not in banned]
    return banned


# --------------------------------------------------------------------------
# per-source normalisation
# --------------------------------------------------------------------------
def steps_of_mp(w):
    return [{"n": s["n"], "title": s["title"], "text": s["text"],
             "methods": s["acts"]} for s in w["steps"]]


def from_mp(w):
    step_acts = sorted({a for s in w["steps"] for a in s["acts"]})
    methods = sorted(set(w["acts"]) | set(step_acts))
    return {
        "id": w["id"], "src": "sshomp", "title": w["title"], "desc": w["desc"],
        "url": w["url"], "lang": (w["langs"] or ["English"])[0],
        "methods": methods, "method_src": "declared",
        "steps": steps_of_mp(w),
        "topics": sorted(set(w["keywords"] + w["disciplines"])),
        "materials": sorted({"in:" + f for f in w["informat"]}
                            | {"out:" + f for f in w["outformat"]}),
        "audience": w["audience"], "licence": w["licence"],
        "text": " ".join([w["title"], w["desc"]]
                         + [s["title"] + " " + s["text"] for s in w["steps"]]),
    }


def from_ph(w):
    return {
        "id": w["id"], "src": "ph", "title": w["title"], "desc": w["desc"],
        "url": w["url"], "lang": "English",
        "methods": [], "method_src": "inferred",
        "ph_goal": sorted({PH_ACT2GOAL.get(a.lower(), "")
                           for a in w["ph_activity"]} - {""}),
        "steps": [{"n": s["n"], "title": s["title"], "text": "", "methods": []}
                  for s in w["steps"]],
        "topics": sorted({t.replace("-", " ") for t in w["keywords"]}),
        "materials": [], "audience": [], "licence": w["licence"],
        "difficulty": w.get("difficulty", ""),
        "text": " ".join([w["title"], w["desc"]]
                         + [s["title"] for s in w["steps"]]),
        "_body": w["text"],
    }


def from_etkad(w, unmapped):
    def en(terms):
        out = []
        for t in terms:
            k = t.strip().lower()
            if k in ET2EN:
                out.append(ET2EN[k])
            else:
                unmapped[t] += 1
        return out

    steps = [{"n": s["n"], "title": s["title"], "text": s.get("text", ""),
              "methods": sorted(set(en(s["tadirah"])))} for s in w["stages"]]
    methods = sorted(set(en(w["tadirah"])))
    # The scraped page text opens with the site's navigation chrome, so the
    # first stage's own prose is a far better one-line description than the
    # head of the document.
    desc = next((s.get("text", "") for s in w["stages"] if s.get("text")), "")
    return {
        "id": w["id"], "src": "etkad", "title": w["title"],
        "desc": desc[:400], "url": w["url"], "lang": "Estonian",
        "methods": methods, "method_src": "declared",
        "steps": steps,
        "topics": sorted(set(w["discipline"] + w["content_kw"])),
        "materials": sorted({"media:" + m for m in w["media"]}
                            | {"out:" + o for o in w["output"]}),
        "audience": [], "licence": w["licence"],
        "text": " ".join([w["title"]] + [s["title"] for s in w["stages"]]),
        "_body": w["text"],
    }


# --------------------------------------------------------------------------
# facets
# --------------------------------------------------------------------------
def flow_features(rec):
    """The shape of a workflow, independent of its subject.

    Two things go in: which goals occupy which quarter of the run (so a workflow
    that captures early and disseminates late looks like every other one that
    does), and which goal follows which (so iteration between enrichment and
    analysis is visible as a backwards edge). Workflows with fewer than three
    tagged steps get nothing — there is no shape to speak of.
    """
    tagged = [(s["n"], sorted({goal_of(m) for m in s["methods"]} - {""}))
              for s in rec["steps"]]
    tagged = [(n, g) for n, g in tagged if g]
    if len(tagged) < 3:
        return []
    last = max(n for n, _ in tagged) or 1
    feats, prev = [], []
    for n, goals in tagged:
        q = min(3, int(4 * n / (last + 1e-9)))
        for g in goals:
            feats.append(f"pos{q}:{g}")
        for a in prev:
            for b in goals:
                if a != b:
                    feats.append(f"{a}>{b}")
        prev = goals
    return feats


def text_features(rec, idf, top=30):
    toks = [t for t in re.findall(r"[a-zà-ÿõäöüšž]{3,}", rec["text"].lower())
            if t not in STOP_TEXT]
    tf = collections.Counter(toks)
    scored = sorted(tf.items(), key=lambda kv: -kv[1] * idf.get(kv[0], 1.0))
    return [w for w, _ in scored[:top]]


def main():
    mp = load("mp_workflows")["workflows"]
    items = load("mp_items")["items"]
    ph = load("ph")["workflows"]
    etk = load("etkad")["workflows"]

    tools, acts = build_gazetteers(items)
    print(f"gazetteer: {len(tools)} tool names, {len(acts)} activity labels")

    unmapped = collections.Counter()
    recs = [from_mp(w) for w in mp] + [from_ph(w) for w in ph] \
        + [from_etkad(w, unmapped) for w in etk]

    # --- inferred methods and named tools, from whatever prose each source has
    for r in recs:
        body = r.pop("_body", "") or r["text"]
        r["tools"] = [t["name"] for t in match_tools(body, tools)]
        if r["method_src"] == "inferred":
            r["methods"] = match_methods(body, acts)
    banned_t = drop_ubiquitous(recs, "tools", 0.35)
    inferred = [r for r in recs if r["method_src"] == "inferred"]
    banned_m = drop_ubiquitous(inferred, "methods", 0.6)
    print(f"dropped as ordinary words: {len(banned_t)} tool names "
          f"{sorted(banned_t)[:6]}, {len(banned_m)} activity labels "
          f"{sorted(banned_m)[:6]}")

    # --- idf over the whole corpus, for the text facet
    df = collections.Counter()
    for r in recs:
        df.update(set(t for t in re.findall(r"[a-zà-ÿõäöüšž]{3,}", r["text"].lower())
                      if t not in STOP_TEXT))
    n = len(recs)
    import math
    idf = {w: math.log(n / (1 + c)) for w, c in df.items()}

    # --- assemble the facets
    for r in recs:
        goals = sorted({goal_of(m) for m in r["methods"]} - {""})
        if not goals and r.get("ph_goal"):
            goals = r["ph_goal"]
        r["goals"] = goals
        r["facets"] = {
            "method": r["methods"],
            "goal": goals,
            "tool": r["tools"],
            "topic": [t.lower() for t in r["topics"]],
            "material": [m.lower() for m in r["materials"]],
            "flow": flow_features(r),
            "text": text_features(r, idf),
        }
        r["nsteps"] = len(r["steps"])
        r["ntagged"] = sum(1 for s in r["steps"] if s["methods"])

    # --- report
    by = collections.Counter(r["src"] for r in recs)
    print(f"\nworkflows: {len(recs)}  " +
          "  ".join(f"{k}={v}" for k, v in sorted(by.items())))
    for f in ["method", "goal", "tool", "topic", "material", "flow", "text"]:
        have = sum(1 for r in recs if r["facets"][f])
        uniq = len({x for r in recs for x in r["facets"][f]})
        print(f"  {f:9} {have:4}/{len(recs)} workflows have it, "
              f"{uniq:5} distinct features")
    if unmapped:
        print("\nEstonian terms with no TaDiRAH2 counterpart:")
        for t, c in unmapped.most_common():
            print(f"  {t}  x{c}  {KNOWN_UNMAPPED.get(t.lower(), '')}")

    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "corpus.json"), "w", encoding="utf-8") as f:
        json.dump({"workflows": recs, "goal_order": GOAL_ORDER,
                   "goal_of": GOAL_OF}, f, ensure_ascii=False)
    print(f"\n-> {os.path.join(WORK, 'corpus.json')}")


if __name__ == "__main__":
    main()
