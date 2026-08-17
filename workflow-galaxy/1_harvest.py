#!/usr/bin/env python3
"""Stage 1: harvest workflows — things that have steps, from three sources.

WHY THIS CORPUS AND NOT THE LAST ONE
------------------------------------
The v1 method galaxy compared *methods* to each other, and workflows only came
along as an afterthought. Here the unit of analysis is the workflow itself, so
every source has to supply something with an order to it.

  SSH Open Marketplace `/workflows`   108 workflows, 729 ordered steps.
        The v1 README said the Marketplace's `step` category was empty. That was
        wrong, and wrong in an interesting way: steps are not indexed by
        item-search, so they are invisible to the facet counts — but they are
        returned inline under `composedOf` on the workflow endpoint, in order,
        with their own TaDiRAH activity properties. 48 workflows tag per step.

  Programming Historian  119 English lessons.
        Each lesson is a tutorial with ordered sections, and the lesson index
        carries PH's own `activity` verb (acquiring / transforming / analyzing /
        presenting / sustaining), topic tags and a difficulty rating — all in one
        page of HTML, so the index costs one request.

  ETKAD  10 Estonian workflows, TaDiRAH-tagged per stage, in order.

Plus the full 6,305-item Marketplace corpus, not as map nodes this time but as
two reference layers: the tool-name gazetteer used to spot software mentioned in
workflow prose, and the background co-occurrence statistics that tell us which
method pairings are ordinary and which are surprising.

Everything is pure HTTP into memory. Nothing is cloned; only small JSON lands on
disk.

Output: work/raw/{mp_workflows,mp_items,ph,etkad}.json
"""
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

WORK = os.path.abspath(os.environ.get("WFA_WORK", "./work"))
RAW = os.path.join(WORK, "raw")
API = "https://marketplace-api.sshopencloud.eu/api"
PH = "https://programminghistorian.org"
UA = {"User-Agent": "etkad-workflow-galaxy/1.0 (research prototype; mark.mets@tlu.ee)"}
TIMEOUT = 60

ETKAD_BASE = "https://www.etkad.ee/humal/toovood/"
ETKAD_SLUGS = [
    "arkamisaja-kirjanduslik-vorgustik-koidula-ja-kreutzwaldi-kirjavahetuse-pohjal",
    "mineviku-elud-eesti-kultuuriandmetes-19-sajandi-vallakohtute-protokollide-ja-"
    "bibliograafiliste-andmete-pohjal-interaktiivsete-rakenduste-arendamine",
    "tartu-ehitusprojektide-interaktiivne-kaart",
    "teraviljadega-seotud-regilaulude-leviku-analuus-eestis",
    "muinasjututuubi-0567a-analuus-seto-imemuinasjuttude-korpuses",
    "eesti-rahvapillimuusika-regionaalsete-ja-ajaliste-mustrite-analuus",
    "tunes-of-the-world-map-eesti-ja-ukraina-rahvalauluparandi-uurimine",
    "era-fotoarhiivi-ruumilised-ja-ajalised-mustrid",
    "suurel-skaalal-ngrammidega",
    "esemeuurija-toofotodes-peituvate-andmete-kasutusvoimalused",
]


def http(url, retries=3, as_json=True):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
            return json.loads(raw) if as_json else raw.decode("utf-8", "replace")
        except Exception as e:                       # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise last


def save(tag, obj):
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, tag + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def load(tag):
    p = os.path.join(RAW, tag + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def unescape(s):
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#8211;", "-"), ("&#8212;", "-"),
                 ("&#8217;", "'"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"),
                 ("&#8220;", '"'), ("&#8221;", '"'), ("&#039;", "'"), ("&#39;", "'")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def strip_tags(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


# --------------------------------------------------------------------------
# Marketplace
# --------------------------------------------------------------------------
def props(item, code):
    """Values of one property type. Concept-typed properties carry a controlled
    label; free-text ones carry a raw value."""
    out = []
    for p in item.get("properties") or []:
        if (p.get("type") or {}).get("code") != code:
            continue
        c = p.get("concept")
        out.append((c.get("label") or c.get("code")) if c else p.get("value"))
    return [str(x).strip() for x in out if x]


def clean(s, n=600):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()[:n]


def mp_workflow(w):
    steps = []
    for i, s in enumerate(w.get("composedOf") or []):
        steps.append({
            "n": i,
            "title": clean(s.get("label"), 160),
            "text": clean(s.get("description"), 700),
            "acts": sorted(set(props(s, "activity"))),
        })
    return {
        "src": "sshomp",
        "id": "mp:" + (w.get("persistentId") or ""),
        "title": clean(w.get("label"), 200),
        "desc": clean(w.get("description"), 900),
        "url": "https://marketplace.sshopencloud.eu/workflow/" + (w.get("persistentId") or ""),
        "acts": sorted(set(props(w, "activity"))),
        "keywords": sorted(set(props(w, "keyword")))[:25],
        "disciplines": sorted(set(props(w, "discipline")))[:8],
        "langs": sorted(set(props(w, "language")))[:6],
        "audience": sorted(set(props(w, "intended-audience")))[:6],
        "informat": sorted(set(props(w, "inputformat")))[:8],
        "outformat": sorted(set(props(w, "outputformat")))[:8],
        "licence": (props(w, "license") or [""])[0],
        "steps": steps,
    }


def harvest_mp_workflows():
    if load("mp_workflows"):
        d = load("mp_workflows")
        print(f"    cached: {len(d['workflows'])} workflows")
        return
    out, page = [], 1
    while True:
        d = http(f"{API}/workflows?page={page}&perpage=50")
        out += [mp_workflow(w) for w in d["workflows"]]
        if page >= d["pages"]:
            break
        page += 1
    steps = sum(len(w["steps"]) for w in out)
    tagged = sum(1 for w in out if any(s["acts"] for s in w["steps"]))
    save("mp_workflows", {"count": len(out), "workflows": out})
    print(f"    -> {len(out)} workflows, {steps} steps, "
          f"{tagged} with per-step activities")


def harvest_mp_items():
    """The whole 6,305-item corpus: gazetteer + background statistics."""
    if load("mp_items"):
        print(f"    cached: {load('mp_items')['count']} items")
        return
    first = http(f"{API}/item-search?perpage=100&page=1")
    pages = first["pages"]
    print(f"    {first['hits']} items across {pages} pages")

    def trim(i):
        return {"id": i.get("persistentId"), "cat": i.get("category"),
                "label": clean(i.get("label"), 200), "desc": clean(i.get("description"), 400),
                "acts": sorted(set(props(i, "activity"))),
                "keywords": sorted(set(props(i, "keyword")))[:15],
                "url": (i.get("accessibleAt") or [""])[0] if i.get("accessibleAt") else ""}

    items = [trim(i) for i in first["items"]]

    def page(n):
        try:
            return [trim(i) for i in http(f"{API}/item-search?perpage=100&page={n}")["items"]]
        except Exception:                            # noqa: BLE001
            print(f"    !! page {n} failed")
            return []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for got in ex.map(page, range(2, pages + 1)):
            items.extend(got)
    save("mp_items", {"count": len(items), "items": items})
    print(f"    -> {len(items)} items "
          f"({sum(1 for i in items if i['acts'])} tagged)")


# --------------------------------------------------------------------------
# Programming Historian
# --------------------------------------------------------------------------
# The lesson index renders every lesson's metadata into spans, so one request
# gets activity + topics + difficulty + abstract for all 119 lessons. Only the
# ordered section headings need the individual pages.
CARD = re.compile(
    r'<a href="(/en/lessons/[a-z0-9\-]+)"><h2 class="title">(.*?)</h2></a>(.{0,2600}?)'
    r'<span class="date">', re.S)
SPAN = re.compile(r'<span class="(activity|topics|difficulty)">(.*?)</span>', re.S)
ABS = re.compile(r'<p class="abstract">(.*?)</p>', re.S)

# PH sections that are apparatus, not steps of the work.
PH_SKIP = re.compile(
    r"^(contents|about the author|acknowledg|bibliograph|works cited|references|"
    r"endnotes|notes|further reading|suggested prior|donate|lesson goals?|"
    r"introduction|conclusion|summary|glossary|appendix|discussion|"
    r"suggested readings?|footnotes|"
    # Byline apparatus. Every lesson carries these as headings, so without them
    # the first six "steps" of every PH workflow were "edited by", "reviewed by",
    # "translated by" and so on.
    r"edited by|reviewed by|translated by|translation edited by|"
    r"translation reviewed by|written by|posted by|prerequisites|"
    r"what you will learn|lesson dataset|before you begin|"
    r"required software|setup|installation|getting started)\b", re.I)


def harvest_ph():
    if load("ph"):
        print(f"    cached: {len(load('ph')['workflows'])} lessons")
        return
    idx = http(PH + "/en/lessons/", as_json=False)
    cards = {}
    for path, title, blob in (m.groups() for m in CARD.finditer(idx)):
        meta = {"activity": [], "topics": [], "difficulty": ""}
        for k, v in SPAN.findall(blob):
            v = unescape(re.sub(r"<[^>]+>", "", v))
            if k == "difficulty":
                meta["difficulty"] = v
            elif v:
                meta[k].append(v)
        a = ABS.search(blob)
        cards[path] = {"title": unescape(title), "meta": meta,
                       "abstract": unescape(re.sub(r"<[^>]+>", "", a.group(1))) if a else ""}
    print(f"    index: {len(cards)} lessons")

    def one(path):
        try:
            html = http(PH + path, as_json=False)
        except Exception:                            # noqa: BLE001
            return None
        body = html.split('id="post"', 1)[-1]
        # Everything above the table of contents is front matter: title, author,
        # editors, reviewers, translators. Cutting there removes the byline in
        # one move, including the bare author name that carries no keyword for a
        # stoplist to catch.
        toc = re.search(r"<h\d[^>]*>\s*Contents\s*</h\d>", body, re.I)
        if toc:
            body = body[toc.end():]
        heads = []
        for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", body, re.S):
            t = unescape(re.sub(r"<[^>]+>", "", m.group(2)))
            t = re.sub(r"^\d+[.)]\s*", "", t).strip()
            if t and not PH_SKIP.match(t) and len(t) < 110 and t not in heads:
                heads.append(t)
        c = cards[path]
        return {
            "src": "ph", "id": "ph:" + path.rsplit("/", 1)[-1],
            "title": c["title"], "desc": c["abstract"], "url": PH + path,
            "acts": [], "ph_activity": c["meta"]["activity"],
            "keywords": c["meta"]["topics"], "disciplines": [], "langs": ["English"],
            "audience": [], "informat": [], "outformat": [],
            "difficulty": c["meta"]["difficulty"], "licence": "CC BY 4.0",
            "steps": [{"n": i, "title": h, "text": "", "acts": []}
                      for i, h in enumerate(heads)],
            "text": strip_tags(body)[:30000],
        }

    with ThreadPoolExecutor(max_workers=8) as ex:
        out = [w for w in ex.map(one, sorted(cards)) if w]
    save("ph", {"count": len(out), "workflows": out})
    steps = sum(len(w["steps"]) for w in out)
    print(f"    -> {len(out)} lessons, {steps} sections "
          f"({steps/max(1,len(out)):.1f} per lesson)")


# --------------------------------------------------------------------------
# ETKAD
# --------------------------------------------------------------------------
STEPS_MARKER = "Töövoo sammud"


def tagged_terms(html, data_type):
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+data-type="' + data_type + r'"[^>]*>(.*?)</a>',
                         html, re.S | re.I):
        lab = unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        if lab and lab.lower() not in seen:
            seen.add(lab.lower())
            out.append(lab)
    return out


def parse_stages(steps_html):
    """One entry per Kadence accordion pane: title, TaDiRAH keywords, body."""
    panes = re.split(r'<div class="wp-block-kadence-pane', steps_html)[1:]
    stages = []
    for p in panes:
        m = re.search(r'class="kt-blocks-accordion-title">(.*?)</span>', p, re.S)
        title = unescape(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        kws = tagged_terms(p, "marksonad")
        # The split lands mid-tag, so the pane text starts with the rest of the
        # opening <div ...> — class names and all. Cut to the end of that tag
        # before stripping, or every stage description opens with
        # `kt-accordion-pane kt-pane1719_6af841-e9">`.
        body = p.split(">", 1)[-1] if ">" in p else p
        if title or kws:
            stages.append({"n": len(stages), "title": title, "tadirah": kws,
                           "text": strip_tags(body)[:1200]})
    return stages


def harvest_etkad():
    if load("etkad"):
        print(f"    cached: {len(load('etkad')['workflows'])} workflows")
        return
    out = []
    for slug in ETKAD_SLUGS:
        url = ETKAD_BASE + slug + "/"
        try:
            html = http(url, as_json=False)
        except Exception as e:                       # noqa: BLE001
            print(f"    !! {slug[:40]}: {type(e).__name__}")
            continue
        head, _, steps = html.partition(STEPS_MARKER)
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        rec = {
            "src": "etkad", "id": "etkad:" + slug[:40], "slug": slug, "url": url,
            "title": (unescape(title.group(1)).split("–")[0].split("|")[0].strip()
                      if title else slug),
            "desc": "",
            "tadirah_top": tagged_terms(head, "marksonad"),
            "tadirah": tagged_terms(html, "marksonad"),
            "discipline": tagged_terms(html, "eriala"),
            "output": tagged_terms(html, "valjund"),
            "media": tagged_terms(html, "andmete-meediatuup"),
            "content_kw": [unescape(re.sub(r"<[^>]+>", "", m.group(1)))
                           for m in re.finditer(
                               r'<a[^>]+href="https://ems\.elnet\.ee/[^"]*"[^>]*>(.*?)</a>',
                               head, re.S)],
            "stages": parse_stages(steps),
            "licence": (re.search(r"Litsents:\s*</strong>\s*(?:<a[^>]*>)?([^<]+)", head)
                        or [None, ""])[1].strip(),
            "text": strip_tags(html)[:24000],
        }
        out.append(rec)
        print(f"    {rec['title'][:44]:46} tadirah={len(rec['tadirah']):2} "
              f"stages={len(rec['stages']):2}")
    save("etkad", {"count": len(out), "workflows": out})


def main():
    os.makedirs(RAW, exist_ok=True)
    print("[1/4] Marketplace workflows (with ordered steps)")
    harvest_mp_workflows()
    print("\n[2/4] Marketplace full corpus (gazetteer + background)")
    harvest_mp_items()
    print("\n[3/4] Programming Historian lessons")
    harvest_ph()
    print("\n[4/4] ETKAD workflow pages")
    harvest_etkad()
    mb = sum(os.path.getsize(os.path.join(RAW, f)) for f in os.listdir(RAW)) / 1e6
    print(f"\nharvest complete - {mb:.1f} MB in {RAW}")


if __name__ == "__main__":
    sel = {"--mp": harvest_mp_workflows, "--items": harvest_mp_items,
           "--ph": harvest_ph, "--etkad": harvest_etkad}
    for a in sys.argv[1:]:
        if a in sel:
            sel[a]()
            sys.exit()
    main()
