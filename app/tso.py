from __future__ import annotations

import html as html_lib
import re
from urllib.parse import urlparse

TSO_SITEMAP = "https://www.treesandshrubsonline.org/sitemap.xml"
TSO_SOURCE = "Trees and Shrubs Online (IDS)"


def scientific_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) < 3:
        return ""
    slug = parts[2].lower()
    prefix_cross = slug.startswith("x-")
    inner_cross = "-x-" in slug
    slug = slug.removeprefix("x-").replace("-x-", "-")
    words = [word for word in slug.split("-") if word]
    if not words:
        return ""
    words[0] = words[0].capitalize()
    if prefix_cross:
        return "× " + " ".join(words)
    if inner_cross and len(words) >= 2:
        return f"{words[0]} × {' '.join(words[1:])}"
    return " ".join(words)


def html_text(value: str) -> str:
    value = re.sub(r"(?is)<script.*?>.*?</script>", " ", value)
    value = re.sub(r"(?is)<style.*?>.*?</style>", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html_lib.unescape(value).replace("\xa0", " ").replace("&ensp;", " ")
    return re.sub(r"\s+", " ", value).strip()


def tso_species_urls(sitemap_xml: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap_xml):
        path_parts = [part for part in urlparse(loc).path.split("/") if part]
        if len(path_parts) != 3 or path_parts[0] != "articles":
            continue
        slug = path_parts[2].lower()
        if "cultivar" in slug:
            continue
        if loc not in seen:
            seen.add(loc)
            urls.append(loc)
    return urls


def _bold_value(html: str, label: str) -> str:
    pattern = rf"<b>{re.escape(label)}(?:\s|&ensp;|:)*</b>\s*(.*?)(?:<p><b>|<div class=tso-main-text|$)"
    match = re.search(pattern, html, re.I | re.S)
    if not match:
        return ""
    chunk = match.group(1)
    countries = [
        html_lib.unescape(name).strip()
        for name in re.findall(r"font-variant:small-caps[^>]*>([^<]+)", chunk)
        if name.strip()
    ]
    if countries:
        return ", ".join(dict.fromkeys(countries))
    return html_text(chunk)


def _list_after_heading(html: str, heading: str) -> list[str]:
    match = re.search(
        rf"<h3[^>]*>{re.escape(heading)}</h3>\s*<ul[^>]*>(.*?)</ul>",
        html,
        re.I | re.S,
    )
    if not match:
        return []
    items = [html_text(item) for item in re.findall(r"<li>(.*?)(?=<li>|$)", match.group(1), re.S)]
    return [item for item in items if item]


def extract_tso_height_ft(text: str) -> str:
    typical = re.findall(r"to\s+(\d+(?:\.\d+)?)\s*m\s+tall", text, re.I)
    typical += re.findall(
        r"(?:evergreen|deciduous)?\s*(?:tree|shrub)\s+to\s+(\d+(?:\.\d+)?)\s*m\b",
        text,
        re.I,
    )
    if typical:
        return str(round(max(float(value) for value in typical) * 3.28084, 1))
    cultivated = re.findall(r"(?:measured at|reached)\s+(\d+(?:\.\d+)?)\s*m\b", text, re.I)
    if cultivated:
        return str(round(max(float(value) for value in cultivated) * 3.28084, 1))
    feet = [int(high) for _low, high in re.findall(r"(\d+)\s*(?:to|–|-)\s*(\d+)\s*ft\b", text, re.I)]
    feet += [int(value) for value in re.findall(r"(\d+)\s*ft\s+tall", text, re.I)]
    if feet:
        return str(max(feet))
    return ""


def parse_tso_article(html: str, url: str) -> dict[str, str] | None:
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if not heading:
        return None
    heading_html = re.sub(r"<span class=authors>.*?</span>", "", heading.group(1), flags=re.I | re.S)
    scientific = html_text(heading_html)
    scientific = re.sub(r"\s+", " ", scientific).strip()
    slug_name = scientific_from_url(url)
    first = scientific.split()[0] if scientific else ""
    if len(first) < 3 or len(scientific.split()) < 2:
        scientific = slug_name
    if not scientific or len(scientific.split()) < 2:
        return None

    main = html
    start = html.find("tso-col-main")
    if start >= 0:
        end = html.find("tso-footer", start)
        main = html[start : end if end > start else start + 40000]

    family_items = _list_after_heading(html, "Family")
    common_items = _list_after_heading(html, "Common Names")
    usda = html_text(_bold_value(main, "USDA Hardiness Zone"))
    rhs = html_text(_bold_value(main, "RHS Hardiness Rating"))
    habitat = html_text(_bold_value(main, "Habitat"))
    distribution = _bold_value(main, "Distribution")
    taxonomic_note = html_text(_bold_value(main, "Taxonomic note"))
    conservation = html_text(_bold_value(main, "Conservation status"))
    height = extract_tso_height_ft(html_text(main))

    provenance = distribution
    main_match = re.search(r"<div class=tso-main-text>(.{0,8000})", html, re.I | re.S)
    main_text = html_text(main_match.group(1) if main_match else "")
    if not provenance:
        lower = main_text.lower()
        for marker in ("native of", "hybrid between", "introduced to", "originated", "garden origin"):
            idx = lower.find(marker)
            if idx < 0:
                continue
            snippet = main_text[idx : idx + 280]
            cutoff = -1
            for match in re.finditer(r"(?<![A-Z])\.\s", snippet):
                cutoff = match.start()
                break
            provenance = snippet[: cutoff + 1].strip() if cutoff > 40 else snippet.strip()
            break

    genus = scientific.split()[0].replace("×", "").strip()
    return {
        "scientific_name": scientific,
        "common_name": common_items[0] if common_items else "",
        "family": family_items[0] if family_items else "",
        "genus": genus,
        "usda_hardiness_zone": usda,
        "rhs_hardiness_rating": rhs,
        "height_mature_ft": height,
        "native_status": provenance[:400],
        "habitat": habitat[:400],
        "taxonomic_note": taxonomic_note[:400],
        "conservation_status": conservation,
        "tso_url": url,
        "catalog_source": TSO_SOURCE,
    }
