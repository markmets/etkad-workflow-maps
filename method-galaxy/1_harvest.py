#!/usr/bin/env python3
"""Stage 1: harvest the DH method corpus.

TWO SOURCES, ONE SHARED VOCABULARY
----------------------------------
SSH Open Marketplace (marketplace.sshopencloud.eu) holds ~6,300 DH tools,
datasets, training materials, publications and workflows. Crucially it tags them
with `tadirah2` — the same TaDiRAH vocabulary ETKAD uses on its own workflow
pages, in Estonian. That shared vocabulary is what lets ~10 Estonian workflows
be plotted inside a field of thousands of European DH objects.

Everything here is pure HTTP into memory; nothing is cloned and nothing but
small JSON touches disk. The Marketplace search API returns item properties
INLINE, so the whole corpus is ~64 requests rather than 6,305.

Output: work/raw/sshomp.json, work/raw/etkad.json
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

WORK = os.path.abspath(os.environ.get("MGAL_WORK", "./work"))
RAW = os.path.join(WORK, "raw")
API = "https://marketplace-api.sshopencloud.eu/api"
UA = {"User-Agent": "etkad-method-galaxy/1.0 (research prototype)",
      "Accept": "application/json"}
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


def done(tag):
    return os.path.exists(os.path.join(RAW, tag + ".json"))


# --------------------------------------------------------------------------
# SSH Open Marketplace
# --------------------------------------------------------------------------
def props(item, code):
    """Property values of one type. Concept-typed properties carry a controlled
    label; free-text ones carry a raw value."""
    out = []
    for p in item.get("properties") or []:
        if (p.get("type") or {}).get("code") != code:
            continue
        c = p.get("concept")
        out.append((c.get("label") or c.get("code")) if c else p.get("value"))
    return [str(x).strip() for x in out if x]


def trim(item):
    return {
        "id": item.get("persistentId"),
        "cat": item.get("category"),
        "label": (item.get("label") or "").strip(),
        "desc": re.sub(r"\s+", " ", (item.get("description") or ""))[:500],
        "url": (item.get("accessibleAt") or [""])[0] if item.get("accessibleAt") else "",
        "activities": sorted(set(props(item, "activity"))),
        "keywords": sorted(set(props(item, "keyword")))[:25],
        "langs": sorted(set(props(item, "language")))[:10],
        "disciplines": sorted(set(props(item, "discipline")))[:8],
        "source": ", ".join(s.get("label", "") for s in (item.get("sources") or [])[:2]),
        "actors": [(c.get("actor") or {}).get("name", "")
                   for c in (item.get("contributors") or [])[:4]],
    }


def harvest_sshomp():
    if done("sshomp"):
        d = json.load(open(os.path.join(RAW, "sshomp.json"), encoding="utf-8"))
        print(f"    cached: {len(d['items'])} items")
        return len(d["items"])

    first = http(f"{API}/item-search?perpage=100&page=1")
    pages, hits = first["pages"], first["hits"]
    print(f"    {hits} items across {pages} pages")
    facets = {g: {k: v.get("count") for k, v in vals.items()}
              for g, vals in (first.get("facets") or {}).items()}

    items = [trim(i) for i in first["items"]]

    def page(n):
        try:
            return [trim(i) for i in http(f"{API}/item-search?perpage=100&page={n}")["items"]]
        except Exception as e:                       # noqa: BLE001
            print(f"    !! page {n} failed: {type(e).__name__}")
            return []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, got in enumerate(ex.map(page, range(2, pages + 1)), 2):
            items.extend(got)
            if i % 15 == 0:
                print(f"    ...page {i}/{pages}, {len(items)} items")

    save("sshomp", {"count": len(items), "items": items, "facets": facets})
    with_act = sum(1 for i in items if i["activities"])
    print(f"    -> {len(items)} items, {with_act} with a TaDiRAH activity "
          f"({100*with_act/max(1,len(items)):.0f}%)")
    return len(items)


# --------------------------------------------------------------------------
# ETKAD workflow pages
# --------------------------------------------------------------------------
# Every controlled term on these pages is a link carrying data-type, e.g.
#   <a href=".../marksonad/kogumine/" data-type="marksonad">kogumine</a>
# so parsing is exact rather than a guess at label text. Four taxonomies are in
# use: marksonad (TaDiRAH, in Estonian), eriala (discipline), valjund (output)
# and andmete-meediatuup (data media type). Content keywords are separate again
# and link to EMS, the Estonian subject thesaurus, with persistent IDs.
#
# Workflow stages are Kadence accordion panes, each with its own title and its
# own TaDiRAH keyword list — so a workflow is a *sequence* of method steps, not
# just a bag of tags. That is the structure the constellation view uses.
STEPS_MARKER = "Töövoo sammud"


def unescape(s):
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#8211;", "–"), ("&#8212;", "—"),
                 ("&#8217;", "'"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"),
                 ("&#8220;", '"'), ("&#8221;", '"'), ("&#039;", "'")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def tagged_terms(html, data_type):
    """Labels of every <a data-type="..."> link, de-duplicated, order kept."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+data-type="' + data_type + r'"[^>]*>(.*?)</a>',
                         html, re.S | re.I):
        lab = unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        if lab and lab.lower() not in seen:
            seen.add(lab.lower())
            out.append(lab)
    return out


def strip_tags(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def parse_stages(steps_html):
    """One entry per accordion pane: its title and its TaDiRAH keywords."""
    panes = re.split(r'<div class="wp-block-kadence-pane', steps_html)[1:]
    stages = []
    for p in panes:
        m = re.search(r'class="kt-blocks-accordion-title">(.*?)</span>', p, re.S)
        title = unescape(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        kws = tagged_terms(p, "marksonad")
        if title or kws:
            stages.append({"title": title, "tadirah": kws})
    return stages


def harvest_etkad():
    if done("etkad"):
        d = json.load(open(os.path.join(RAW, "etkad.json"), encoding="utf-8"))
        print(f"    cached: {len(d['workflows'])} workflows")
        return len(d["workflows"])
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
            "slug": slug, "url": url,
            "title": unescape(title.group(1)).split("–")[0].split("|")[0].strip()
                     if title else slug,
            "tadirah_top": tagged_terms(head, "marksonad"),
            "tadirah": tagged_terms(html, "marksonad"),   # union incl. stages
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
            "date": (re.search(r"Kuup[äa]ev[^:]*:\s*</strong>\s*([^<]+)", head)
                     or [None, ""])[1].strip(),
            "authors": [unescape(re.sub(r"<[^>]+>", "", x)) for x in
                        re.findall(r"<li>([^<]*\([^)]*(?:[ÜUÕO]likool|Muuseum|Arhiiv|"
                                   r"Instituut)[^)]*\))</li>", head)][:6],
            "text": strip_tags(html)[:24000],
        }
        out.append(rec)
        print(f"    {rec['title'][:46]:48} tadirah={len(rec['tadirah']):2} "
              f"stages={len(rec['stages']):2} eriala={len(rec['discipline'])}")
    save("etkad", {"count": len(out), "workflows": out})
    return len(out)


def main():
    os.makedirs(RAW, exist_ok=True)
    print("[1/2] SSH Open Marketplace")
    harvest_sshomp()
    print("\n[2/2] ETKAD workflow pages")
    harvest_etkad()
    mb = sum(os.path.getsize(os.path.join(RAW, f)) for f in os.listdir(RAW)) / 1e6
    print(f"\nharvest complete — {mb:.1f} MB in {RAW}")


if __name__ == "__main__":
    if "--etkad" in sys.argv:
        harvest_etkad()
    elif "--sshomp" in sys.argv:
        harvest_sshomp()
    else:
        main()
