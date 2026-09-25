#!/usr/bin/env python3
"""Stage 2: join ETKAD's Estonian TaDiRAH terms to the Marketplace's English ones.

TaDiRAH's own SKOS vocabulary at vocabs.dariah.eu publishes English labels only
(`"languages": ["en"]`), so ETKAD's Estonian terms are a local translation and
the join has to be made here. ET2EN below is that mapping, checked term by term
against the 147 activity labels actually present in the Marketplace.

Unmapped Estonian terms are reported rather than silently dropped — they are
interesting in their own right, because they are the points where Estonian
practice has named something TaDiRAH2 does not cover.

Output: work/corpus.json
"""
import collections
import json
import os
import re

WORK = os.path.abspath(os.environ.get("MGAL_WORK", "./work"))
RAW = os.path.join(WORK, "raw")

# Estonian (etkad.ee/marksonad) -> English (TaDiRAH2 label used by SSHOMP).
ET2EN = {
    "analüüsimine": "Analyzing",
    "andmekaeve": "Data Mining",
    "andmete graafiline kujutamine": "Plotting",
    "andmete kogumine": "Collecting",
    "andmete puhastamine": "Data Cleansing",
    "andmete vastendus": "Data Mapping",
    "andmete visualiseerimine": "Data Visualization",
    "annoteerimine": "Annotating",
    "arhiveerimine": "Archiving",
    "arutamine": "Discussing",
    "avaldamine": "Publishing",
    "avastamine": "Discovering",
    "diagrammide koostamine": "Diagramming",
    "disain": "Designing",
    "eeltöötlus": "Preprocessing",
    "ekstraheerimine": "Extracting",
    "geoviitamine": "Georeferencing",
    "graafika, programmeerimine": "Graphics Programming",
    "haldus": "Managing",
    "identifitseerimine": "Identifying",
    "infootsing": "Information Retrieval",
    "järjestuste joondamine": "Sequence Alignment",
    "kärpimine": "Cropping",
    "kataloogimine": "Cataloging",
    "kirjutamine": "Creating",
    "klasteranalüüs": "Cluster Analysis",
    "kogumine": "Collecting",
    "kollatsioonimine": "Collating",
    "kontekstualiseerimine": "Contextualizing",
    "kontseptualiseerimine": "Conceptualizing",
    "koostamine": "Compiling",
    "korraldamine": "Organizing",
    "kujutuvastus": "Pattern Recognition",
    "lemmatiseerimine": "Lemmatizing",
    "levitamine": "Disseminating",
    "link-avaandmed": "Linked Open Data",
    "loomine": "Creating",
    "loomuliku keele töötlemine": "Natural Language Processing",
    "mängustamine": "Gamification",
    "märgendamine": "Tagging",
    "märgituvastus": "Data Recognition",
    "masinõpe": "Machine Learning",
    "meelsusanalüüs": "Sentiment Analysis",
    "modelleerimine": "Modeling",
    "nimede kasutamise reeglid": "Naming Convention",
    "nimeüksuste tuvastamine": "Named Entity Recognition",
    "optiline märgituvastus": "Optical Character Recognition",
    "optiline noodituvastus": "Optical Music Recognition",
    "otsing": "Searching",
    "päringud": "Querying",
    "põhikomponentide analüüs": "Principal Component Analysis",
    "põhjendamine": "Explanation",
    "postitamine": "Posting",
    "programmeerimine": "Programming",
    "püsi-identifikaator": "Persistent Identifier",
    "rikastamine": "Enriching",
    "ruumiandmete analüüs": "Spatial Analysis",
    "säilitamine": "Preserving",
    "selgitamine": "Explanation",
    "seosanalüüs": "Relational Analysis",
    "sirvimine": "Browsing",
    "sisuanalüüs": "Content Analysis",
    "stiilianalüüs": "Stylistic Analysis",
    "teadmuse avastamine": "Knowledge Discovery",
    "teemade modelleerimine": "Topic Modeling",
    "teisendamine": "Transformation",
    "teisendus": "Transformation",
    "teksti kategoriseerimine": "Text Categorization",
    "teooria loomine": "Theorizing",
    "toimetamine": "Editing",
    "tõlgendamine": "Interpreting",
    "tõlkimine": "Translating",
    "transkodeerimine": "Transcoding",
    "uurimine": "Exploration",
    "vastendus": "Mapping",
    "veebikaapimine": "Web Scraping",
    "visuaalne analüüs": "Visual Analysis",
    "võrdlemine": "Comparing",
}

# Estonian terms with no TaDiRAH2 counterpart. Kept deliberately: each one is a
# small piece of evidence that the vocabulary does not fit local practice.
KNOWN_UNMAPPED = {
    "eemaldamine": "removing — no TaDiRAH2 equivalent",
    "kauguse mõõtmine": "distance measures — in TaDiRAH v1, dropped in v2",
    "süntaksianalüüs": "syntactic analysis — no TaDiRAH2 equivalent",
}

# TaDiRAH's own top-level goal groups, used to colour and group the method map.
GROUPS = {
    "Capture": ["Capturing", "Collecting", "Gathering", "Recording", "Imaging",
                "Photographing", "Transcribing", "Scanning", "Data Recognition",
                "Optical Character Recognition", "Optical Music Recognition",
                "Speech Recognizing", "Audio Recording", "Video Capture",
                "Web Crawling", "Web Scraping", "Data Ingestion", "Upload",
                "Crowdsourcing", "Pattern Recognition", "Genre Recognition"],
    "Creation": ["Creating", "Designing", "Programming", "Graphics Programming",
                 "Web Development", "Wireframing", "Writing", "Translating",
                 "Debugging", "Editing", "Formatting", "Lettering", "Diagramming",
                 "Plotting", "Gamification"],
    "Enrichment": ["Enriching", "Annotating", "Tagging", "Visual Annotation",
                   "Audio Annotation", "Lemmatizing", "POS-Tagging",
                   "Tree-Tagging", "Cleaning", "Data Cleansing", "Preprocessing",
                   "Semantification", "Linked Open Data", "Encoding",
                   "Segmenting", "Correcting", "Improving", "Adding",
                   "Highlighting", "Named Entity Recognition"],
    "Analysis": ["Analyzing", "Content Analysis", "Network Analysis",
                 "Relational Analysis", "Structural Analysis", "Visual Analysis",
                 "Spatial Analysis", "Stylistic Analysis", "Discourse Analysis",
                 "Rhetorical Analysis", "Contrastive Analysis",
                 "Collocation Analysis", "Cluster Analysis", "Topic Modeling",
                 "Sentiment Analysis", "Machine Learning", "Data Mining",
                 "Information Mining", "Knowledge Discovery",
                 "Knowledge Extraction", "Text Categorization", "Extracting",
                 "Co-Occurrence", "Authorship Attribution",
                 "Principal Component Analysis", "Sequence Alignment",
                 "Natural Language Processing", "Modeling", "Comparing",
                 "Data Visualization", "Mapping", "Data Mapping",
                 "Georeferencing", "Identifying"],
    "Interpretation": ["Interpreting", "Contextualizing", "Conceptualizing",
                       "Theorizing", "Explanation", "Description", "Defining",
                       "Abstract Thinking", "Associating", "Associate"],
    "Storage": ["Storing", "Archiving", "Preserving", "Preservation Metadata",
                "Bit Stream Preservation", "Migration", "Replication",
                "Cataloging", "Organizing", "Managing", "Identifier",
                "Persistent Identifier", "Digital Object Identifier",
                "Uniform Resource Identifier", "Naming Convention",
                "Integrating", "Merging", "Aggregating", "Compiling",
                "Converting", "Transformation", "Transcoding", "Modifying",
                "Cropping", "Collating"],
    "Dissemination": ["Disseminating", "Sharing", "Publishing",
                      "Digital Publishing", "Academic Publishing",
                      "Collaborating", "Discussing", "Teaching", "Posting",
                      "Social Networking", "Instant Messaging",
                      "Text Messaging", "Tweet", "User Generated Content",
                      "Audio Conferencing", "Video Conference", "Video Editing"],
    "Discovery": ["Discovering", "Searching", "Browsing", "Exploration",
                  "Finding", "Querying", "Information Retrieval"],
}
GROUP_OF = {a: g for g, acts in GROUPS.items() for a in acts}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


# Marketplace tool labels that are ordinary words or phrases. Matching these
# against Estonian prose produces nonsense hits ("Creating a corpus of texts"
# appearing because the page says "korpus"), so they are excluded from the
# name-matching pass below.
TOOL_MATCH_STOP = {
    "corpus", "text", "data", "search", "atlas", "archive", "library", "map",
    "maps", "notes", "index", "reader", "editor", "viewer", "browser", "player",
    "converter", "images", "image", "audio", "video", "table", "graph", "chart",
    "portal", "platform", "cloud", "toolbox", "toolkit", "suite", "wiki",
    "collection", "database", "repository", "service", "services", "project",
    "projects", "software", "tools", "tool", "python", "java", "word", "excel",
    "access", "english", "estonian", "read", "more", "home", "news", "contact",
    # Estonian function words that collide with Marketplace tool names.
    # `Ning` is a real platform; it is also the Estonian word for "and".
    "ning", "kaart", "kaardid", "andmed", "tekst", "pilt", "aeg", "koht",
    # English words that collide, now that the ETKAD text is the English version
    # of each page. Taken from workflow-galaxy's list, which met them first.
    "words", "select", "topic", "topics", "topic modeling", "topic modelling",
    "things", "origin", "icon", "icons", "pattern", "patterns", "concordance",
    "hypotheses", "annotations", "annotation", "spatial", "sentiment",
    "similarity", "keywords", "metadata", "citation", "citations",
    "transcription", "visualisation", "visualization", "classification",
    "recognition", "processing", "papers", "gazetteer", "dictionary",
    "encyclopedia", "timeline", "concordancer", "compare", "explore",
}


# A tool name that could not be mistaken for a plain word: a digit, a capital
# after the first letter, or punctuation inside it. Same as workflow-galaxy.
# Only a lowercase-to-capital change inside a word counts as an internal
# capital (OpenRefine, EstNLTK). A capital after a space made Title Case phrases
# such as "Time Periods" distinctive, and all-caps names such as BASE and TAGS
# then matched "base form" and "metadata tags".
DISTINCTIVE = re.compile(r"[0-9]|[a-z][A-Z]|[._/+-]")


def tools_named_in_text(text, tool_labels):
    """Marketplace tools whose name literally appears in a workflow's prose.

    A far stronger link than shared method tags: the workflow *says* it used the
    thing. Word-boundary matching on the leading proper-name part, with two
    guards learned the hard way — do not split on a bare hyphen (it turned
    `english-corpora.org` into `english`, which then matched the page's language
    switcher), and require four characters so short real names like QGIS survive.

    Matching is case-sensitive unless the name could not be mistaken for a word
    (a digit, an internal capital, punctuation). While the ETKAD text was Estonian,
    case did not matter; in the English versions Marketplace tools called Topic,
    Pattern, Processing and Spatial fired on ordinary prose. Same rule as
    workflow-galaxy's matcher.
    """
    hits = []
    for pid, label in tool_labels:
        nm = label.strip()
        if len(nm) < 4:
            continue
        # Split only on separators that are followed by prose, never a bare "-",
        # so hyphenated names such as READ-IT stay intact.
        head = re.split(r":| – | — | - |\(", nm)[0].strip()
        if len(head) < 4 or head.lower() in TOOL_MATCH_STOP:
            continue
        flags = re.I if DISTINCTIVE.search(head) else 0
        if re.search(r"(?<![\w])" + re.escape(head) + r"(?![\w])", text, flags):
            hits.append({"id": pid, "name": nm})
    return hits[:20]


def drop_ubiquitous_matches(workflows, ratio=0.6):
    """Any 'tool' matched in most workflows is a false positive.

    Ten unrelated humanities workflows do not all use the same software. A name
    that hits in six or more of them is matching an ordinary word, not a tool —
    a cheap corpus-driven filter that catches collisions no hand-written
    stoplist anticipates.
    """
    seen = collections.Counter()
    for w in workflows:
        for t in w["named_tools"]:
            seen[t["name"]] += 1
    limit = max(2, int(len(workflows) * ratio))
    banned = {n for n, c in seen.items() if c >= limit}
    for w in workflows:
        w["named_tools"] = [t for t in w["named_tools"] if t["name"] not in banned]
    return banned


def main():
    sshomp = json.load(open(os.path.join(RAW, "sshomp.json"), encoding="utf-8"))
    etkad = json.load(open(os.path.join(RAW, "etkad.json"), encoding="utf-8"))

    # --- Marketplace items ---------------------------------------------------
    items = {}
    for it in sshomp["items"]:
        acts = sorted({norm(a) for a in it["activities"] if norm(a)})
        if not acts:
            continue                      # no method tags -> cannot be placed
        items["shomp:" + it["id"]] = {
            "id": "shomp:" + it["id"], "label": it["label"] or it["id"],
            "acts": acts, "cat": it["cat"], "desc": it["desc"], "url": it["url"],
            "src": it["source"], "kw": it["keywords"], "langs": it["langs"],
            "origin": "sshomp",
        }
    print(f"Marketplace: {len(items)} of {sshomp['count']} items carry a TaDiRAH activity")
    by_cat = collections.Counter(v["cat"] for v in items.values())
    print("  by category:", dict(by_cat))

    # --- ETKAD workflows, translated ----------------------------------------
    # Marketplace tool names, used to find direct mentions in the workflow prose
    # (the English version of each page where there is one).
    tool_labels = [("shomp:" + it["id"], it["label"]) for it in sshomp["items"]
                   if it["cat"] == "tool-or-service" and it["label"]]
    print(f"\nmatching {len(tool_labels)} Marketplace tool names against workflow prose")

    unmapped = collections.Counter()
    etkad_nodes = []
    for w in etkad["workflows"]:
        def tr(terms):
            out = []
            for t in terms:
                en = ET2EN.get(norm(t).lower())
                if en:
                    out.append(en)
                else:
                    unmapped[norm(t).lower()] += 1
            return sorted(set(out))

        acts = tr(w["tadirah"])
        stages = [{"title": s["title"], "acts": tr(s["tadirah"])}
                  for s in w.get("stages", [])]
        stages = [s for s in stages if s["acts"]]
        if not acts:
            print(f"  !! no mappable activities: {w['title'][:50]}")
            continue
        wid = "etkad:" + w["slug"][:40]
        items[wid] = {
            "id": wid, "label": w["title"], "acts": acts, "cat": "etkad-workflow",
            "desc": norm(w.get("text", ""))[:400], "url": w["url"],
            "src": "ETKAD HUM andmelabor", "kw": w.get("content_kw", []),
            "langs": ["Estonian"], "origin": "etkad", "url_et": w.get("url_et", w["url"]),
            "disciplines": w.get("discipline", []), "output": w.get("output", []),
            "media": w.get("media", []), "licence": w.get("licence", ""),
            "authors": w.get("authors", []), "stages": stages,
            "et_terms": w["tadirah"],
            "named_tools": tools_named_in_text(w.get("text", ""), tool_labels),
        }
        etkad_nodes.append(wid)
        print(f"  {w['title'][:44]:46} {len(acts):2} activities, {len(stages)} staged, "
              f"{len(items[wid]['named_tools'])} tools named")

    banned = drop_ubiquitous_matches([items[w] for w in etkad_nodes])
    if banned:
        print(f"\ndropped {len(banned)} name collisions matched across most "
              f"workflows: {', '.join(sorted(banned)[:6])}")
    for w in etkad_nodes:
        print(f"  {items[w]['label'][:40]:42} tools: "
              f"{', '.join(t['name'][:26] for t in items[w]['named_tools']) or '—'}")

    if unmapped:
        print("\nEstonian terms with no TaDiRAH2 counterpart:")
        for t, n in unmapped.most_common():
            note = KNOWN_UNMAPPED.get(t, "")
            print(f"   {t:34} x{n}  {note}")

    # --- activity vocabulary -------------------------------------------------
    freq = collections.Counter()
    for v in items.values():
        freq.update(v["acts"])
    etkad_freq = collections.Counter()
    for wid in etkad_nodes:
        etkad_freq.update(items[wid]["acts"])

    # English -> Estonian, so method nodes can carry both labels. Several
    # Estonian terms map to the same English one (kogumine / andmete kogumine ->
    # Collecting); the shortest is the better display form.
    en2et = {}
    for et, en in ET2EN.items():
        if en not in en2et or len(et) < len(en2et[en]):
            en2et[en] = et

    acts = {a: {"n": c, "etkad": etkad_freq.get(a, 0),
                "group": GROUP_OF.get(a, "Other"),
                "et": en2et.get(a, "")} for a, c in freq.items()}
    print(f"Estonian label available for {sum(1 for a in acts if acts[a]['et'])} "
          f"of {len(acts)} methods")
    print(f"\n{len(acts)} distinct activities; "
          f"{sum(1 for a in acts if acts[a]['etkad'])} used by ETKAD")
    ungrouped = [a for a in acts if a not in GROUP_OF]
    if ungrouped:
        print(f"  ungrouped ({len(ungrouped)}): {sorted(ungrouped)[:12]}")

    json.dump({"items": items, "activities": acts, "etkad": etkad_nodes,
               "groups": sorted(GROUPS)},
              open(os.path.join(WORK, "corpus.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"-> {os.path.join(WORK, 'corpus.json')}")


if __name__ == "__main__":
    main()
