"""Scrape algo.monster/liteproblems/{id} for description + Python/Java/C++ solutions.

Selectors discovered by inspecting the SSR'd HTML (no JS rendering needed):
  - Title:                <h1>{N}. {Title} - In-Depth Explanation</h1>
  - Section blocks:       <section> ... <h2 class="_id__learningBlockTitle__nKQlS">{Section}</h2>
                          followed by <div class="MarkdownRenderer_markdown__OXPld"> ... </div>
  - Solution implementation tabs:
        <div role="tabpanel" id="react-aria-N-tabpane-{python|java|cpp|typescript}">
            <pre class="CodeBlock_codeBlock__96Xj8">
                <code class="language-{lang}">  ... lots of nested spans ... </code>
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser, Node

UA = "Mozilla/5.0 (X11; Linux x86_64) interview-prep/0.1"
BASE = "https://algo.monster/liteproblems"

SECTIONS_OF_INTEREST = {
    "Problem Description": "description_md",
    "Example Walkthrough": "walkthrough_md",
    "Time and Space Complexity": "complexity_md",
}

LANGS = {"python", "java", "cpp"}


@dataclass
class ScrapedProblem:
    id: int
    title: str
    description_md: str = ""
    examples: list[dict] = field(default_factory=list)
    constraints_md: str = ""
    walkthrough_md: str = ""
    complexity_md: str = ""
    solutions: dict[str, str] = field(default_factory=dict)  # lang -> code

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description_md": self.description_md,
            "examples_json": json.dumps(self.examples),
            "constraints_md": self.constraints_md,
            "walkthrough_md": self.walkthrough_md,
            "complexity_md": self.complexity_md,
            "solutions": self.solutions,
        }


def _strip_linenum_spans(code_node: Node) -> str:
    """Walk the <code> node, drop line-number spans, concatenate text from the rest."""
    parts: list[str] = []

    def walk(n: Node) -> None:
        # selectolax exposes attributes via .attributes
        attrs = n.attributes or {}
        cls = attrs.get("class") or ""
        if "linenumber" in cls:
            return  # skip the gutter
        # text node
        if not n.tag or n.tag == "-text":
            t = n.text(deep=False) if hasattr(n, "text") else ""
            if t:
                parts.append(t)
            return
        for child in n.iter(include_text=True):
            walk(child)

    # Easier: use raw text and post-process. selectolax gives concatenated text.
    raw = code_node.text(deep=True, separator="")
    # Drop leading line numbers (sequence of digits at start of each visual line):
    # The HTML preserves real newlines between lines, and line numbers appear
    # as standalone digit runs. We strip line-number spans by class first via
    # selectolax tree manipulation, then return the concatenated text.
    for ln in code_node.css("span.linenumber, span.react-syntax-highlighter-line-number"):
        ln.decompose()
    return code_node.text(deep=True, separator="")


def parse_problem(html: str, problem_id: int) -> ScrapedProblem:
    tree = HTMLParser(html)

    # Title
    h1 = tree.css_first("h1")
    title_raw = h1.text(deep=True).strip() if h1 else f"Problem {problem_id}"
    # Strip the suffix "- In-Depth Explanation" and the leading "{N}. "
    title = re.sub(r"\s*-\s*In-Depth Explanation\s*$", "", title_raw)
    title = re.sub(r"^\d+\.\s*", "", title)

    out = ScrapedProblem(id=problem_id, title=title)

    # Sections — find each h2 with the learningBlockTitle class, then the next markdown div
    for h2 in tree.css("h2._id__learningBlockTitle__nKQlS"):
        name = h2.text(deep=True).strip()
        # Find the section's content: walk forward to the next MarkdownRenderer div
        section = h2.parent
        if not section:
            continue
        md_div = section.css_first("div.MarkdownRenderer_markdown__OXPld")
        md_text = md_div.html if md_div else ""

        if name in SECTIONS_OF_INTEREST:
            field_name = SECTIONS_OF_INTEREST[name]
            setattr(out, field_name, md_text or "")

    # Constraints sometimes appear inside the Problem Description block. Try to split.
    desc = out.description_md
    if desc:
        # Heuristic: split on "<strong>Constraints" or markdown "Constraints:"
        m = re.search(r"(?:<strong>|<h[34][^>]*>)\s*Constraints", desc, re.IGNORECASE)
        if m:
            out.constraints_md = desc[m.start():]
            out.description_md = desc[: m.start()].rstrip()

    # Solutions: per-language tabpanels
    for lang in LANGS:
        tab = tree.css_first(f'div[id$="-tabpane-{lang}"]')
        if not tab:
            continue
        code = tab.css_first("code")
        if not code:
            continue
        out.solutions[lang] = _strip_linenum_spans(code).rstrip() + "\n"

    return out


def fetch_html(problem_id: int, cache_dir: Path | None = None) -> str:
    """Fetch and optionally cache raw HTML for replay."""
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{problem_id}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8")
    url = f"{BASE}/{problem_id}"
    with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    if cache_dir:
        (cache_dir / f"{problem_id}.html").write_text(html, encoding="utf-8")
    return html


def scrape(
    problem_id: int,
    cache_dir: Path | None = None,
    rate_limit_s: float = 1.0,
) -> ScrapedProblem:
    html = fetch_html(problem_id, cache_dir=cache_dir)
    if rate_limit_s:
        time.sleep(rate_limit_s)
    return parse_problem(html, problem_id)
