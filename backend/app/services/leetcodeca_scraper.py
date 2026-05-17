"""Scrape leetcode.ca for problem descriptions and Python/C++/Java solutions.

Page structure:
  - article.blog-post contains everything
  - <h2>Description</h2>  … HTML content …  <h2>Solutions</h2>
  - Solutions in div.language-java / div.language-cpp / div.language-py blocks
  - Constraints typically appear as the last <ul> in the description under a "Constraints" heading

URL enumeration: fetch sitemap.xml which lists all ~3800+ problem URLs in the format
  https://leetcode.ca/YYYY-MM-DD-{id}-{Title-Slug}/
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser

UA = "Mozilla/5.0 (X11; Linux x86_64) interview-prep/0.1"
SITEMAP_URL = "https://leetcode.ca/sitemap.xml"

LANG_CLASS = {
    "python": "language-py",
    "cpp":    "language-cpp",
    "java":   "language-java",
}


@dataclass
class ScrapedProblem:
    id: int
    title: str = ""
    description_md: str = ""
    constraints_md: str = ""
    solutions: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

def fetch_id_url_map(cache_path: Path | None = None) -> dict[int, str]:
    """Return {problem_id: page_url} parsed from the sitemap."""
    if cache_path and cache_path.exists():
        xml = cache_path.read_text(encoding="utf-8")
    else:
        with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
            xml = client.get(SITEMAP_URL).text
        if cache_path:
            cache_path.write_text(xml, encoding="utf-8")

    mapping: dict[int, str] = {}
    for url in re.findall(r"<loc>(https://leetcode\.ca/[^<]+)</loc>", xml):
        m = re.search(r"/\d{4}-\d{2}-\d{2}-(\d+)-", url)
        if m:
            mapping[int(m.group(1))] = url
    return mapping


# ---------------------------------------------------------------------------
# Page scraping
# ---------------------------------------------------------------------------

def _extract_code(tree: HTMLParser, lang_css_class: str) -> str:
    div = tree.css_first(f"div.{lang_css_class}")
    if not div:
        return ""
    code = div.css_first("code") or div.css_first("pre")
    return code.text(deep=True).rstrip() + "\n" if code else ""


def parse_problem(html: str, problem_id: int) -> ScrapedProblem:
    tree = HTMLParser(html)
    out = ScrapedProblem(id=problem_id)

    # Title: second h1 has "NNN. Title" format; first has "NNN - Title"
    for h1 in tree.css("h1"):
        t = h1.text(deep=True).strip()
        if re.match(r"\d+\.\s", t):
            out.title = re.sub(r"^\d+\.\s*", "", t).strip()
            break
    if not out.title:
        h1 = tree.css_first("h1")
        if h1:
            out.title = re.sub(r"^\d+[\s\-\.]+", "", h1.text(deep=True).strip()).strip()

    # Description block: everything between <h2>Description</h2> and <h2>Solutions</h2>
    article = tree.css_first("article")
    article_html = article.html if article else tree.html or ""

    desc_match = re.search(
        r"<h2[^>]*>\s*Description\s*</h2>(.*?)<h2[^>]*>\s*Solutions?\s*</h2>",
        article_html,
        re.DOTALL | re.IGNORECASE,
    )
    desc_html = desc_match.group(1).strip() if desc_match else ""

    # Split constraints out of description (look for a "Constraints" section)
    constraints_split = re.search(
        r"(<(?:p|ul|ol|strong)[^>]*>[^<]*[Cc]onstraints[^<]*</(?:p|ul|ol|strong)>.*)",
        desc_html,
        re.DOTALL,
    )
    if constraints_split:
        out.constraints_md = constraints_split.group(1).strip()
        out.description_md = desc_html[: constraints_split.start()].strip()
    else:
        out.description_md = desc_html

    # Solutions
    for lang, css_cls in LANG_CLASS.items():
        code = _extract_code(tree, css_cls)
        if code:
            out.solutions[lang] = code

    return out


def fetch_html(url: str, cache_dir: Path | None = None) -> str:
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w-]", "_", url.rstrip("/").rsplit("/", 1)[-1])
        cached = cache_dir / f"lca_{slug}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8")
    with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    if cache_dir:
        cached.write_text(html, encoding="utf-8")
    return html


def scrape(
    problem_id: int,
    url: str,
    cache_dir: Path | None = None,
    rate_limit_s: float = 1.0,
) -> ScrapedProblem:
    html = fetch_html(url, cache_dir=cache_dir)
    if rate_limit_s:
        time.sleep(rate_limit_s)
    return parse_problem(html, problem_id)
