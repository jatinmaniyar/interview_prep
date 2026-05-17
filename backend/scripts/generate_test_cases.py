"""Generate test cases for problems using Claude Code CLI (claude -p).

Usage:
    python -m scripts.generate_test_cases [--limit N] [--problem-id ID] [--debug]

Strategy:
  - Claude generates INPUTS ONLY (no expected outputs) — avoids slow algorithm tracing.
  - Expected outputs are computed by running the reference Python solution locally.
  - 2 claude calls per problem: one for boilerplate, one for all inputs.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution, TestCase  # noqa: E402
from app.runner.python_runner import extract_runnable_solution, run_python  # noqa: E402

GENERATED_BY = "claude-code-cli"
CALL_TIMEOUT = 120  # seconds

BOILERPLATE_PROMPT = """\
Return ONLY a JSON object with two fields: "boilerplate_python" and "test_harness_python".

"boilerplate_python": a LeetCode-style Python Solution class stub with the exact method name, \
parameter names, type hints, and return type. Add needed imports (List, Optional, TreeNode …) \
as a comment above the class. \
Example: "class Solution:\\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\\n        pass\\n"

"test_harness_python": null if the standard runner handles this problem; otherwise a complete \
Python harness string. The standard runner creates one Solution(), calls method(*args) \
directly with JSON-decoded test args, and JSON-serializes the return value. \
Provide a custom harness when the problem needs platform-injected helpers (read4, guess, \
isBadVersion …), output-buffer arguments (like buf in read problems) that are not real inputs, \
or multiple ordered calls to the same instance per test case.

Custom harness rules:
- Begin with this exact boilerplate (keep ListNode/TreeNode):
    from __future__ import annotations
    import json, sys
    from typing import Optional, List, Dict, Tuple, Set, Any, Union
    class ListNode:
        def __init__(self, val=0, next=None):
            self.val = val; self.next = next
    class TreeNode:
        def __init__(self, val=0, left=None, right=None):
            self.val = val; self.left = left; self.right = right
- Use the literal text {{user_code}} where the Solution class is injected (single braces, \
  will be replaced by simple string substitution — no need to escape other braces)
- Read payload = json.loads(sys.stdin.read()); args = payload["args"] from stdin
- Write json.dumps(result) to stdout (no newline required)
- For read4 problems: args[0]=file-content string, args[1]=int n OR list-of-ints for \
  multiple calls. Mock read4 by reading from list(args[0]). \
  If args[1] is a list: create one Solution(), call read(buf, n) per entry, return list of counts. \
  If args[1] is an int: single call, return the count. buf = ['']*(max(n,200)).

Problem: {title}
{description}
{constraints}"""

INPUTS_PROMPT = """\
Generate test inputs for this LeetCode problem.

Problem: {title}
{description}

CONSTRAINTS (every input MUST satisfy ALL of these — out-of-range inputs will be dropped):
{constraints}

Output a JSON array of {total} items, each exactly: \
{{"input_json": "<JSON-encoded string containing a JSON array of args>", "category": "<label>", "rationale": "<5 words max>"}}.

Categories (do not deviate from counts):
- 4 "sample"     — copy inputs straight from the problem examples
- 16 "edge"      — boundary of constraints: min n, max n (if max is small enough), empty/single-element collections, all-same values, smallest/largest allowed numeric values
- 20 "corner"    — sorted, reverse-sorted, alternating, all-identical, duplicates, mixed boundary values — all still within constraints
- 20 "functional"— typical valid inputs of varied sizes within constraints
- 10 "adversarial"— inputs that commonly expose off-by-one, greedy, or base-case bugs (still within constraints)

Per-item check before emitting (do this mentally for each one):
1. Are all values within the stated constraints? (length bounds, value bounds, allowed characters, required structure)
2. Does the structure match the method signature exactly?
3. Is the JSON syntactically valid? (see rules below)

JSON validity (STRICT — invalid items are silently dropped):
- input_json is a JSON STRING. Inside the string is valid JSON.
- Numbers: -500 NOT "- 500"; no spaces between sign and digits; no underscores; no leading +.
- Booleans/null: lowercase true / false / null (never True/False/None).
- Strings: double-quoted only; escape internal quotes as \\".
- NO trailing commas before ] or }}.
- Every [ matches a ]; every {{ matches a }}. Re-count brackets mentally for each item.
{format_section}
Emit the JSON array now. No prose, no markdown, no explanation."""

DEFAULT_FORMAT_SECTION = (
    "- input_json is a JSON array of positional arguments matching the method signature.\n"
)

CUSTOM_HARNESS_FORMAT_SECTION = """\
- input_json must match the format consumed by this test harness (look at how it reads
  payload["args"] from stdin to derive the correct structure):
```python
{harness}
```
"""


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _call(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-sonnet-4-6"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=CALL_TIMEOUT,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[:300]}")
    return result.stdout.strip()


def _unwrap_json(raw: str) -> object:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _extract_objects(text: str) -> list[dict]:
    """Best-effort: scan text for top-level JSON objects and parse each independently.
    Used when the full response array is malformed (one bad item poisons the whole parse).
    Returns objects that parse cleanly; skips ones that don't."""
    objs: list[dict] = []
    decoder = json.JSONDecoder()
    i = 0
    while i < len(text):
        j = text.find("{", i)
        if j < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, j)
            if isinstance(obj, dict):
                objs.append(obj)
            i = end
        except json.JSONDecodeError:
            i = j + 1
    return objs


_FIX_NEG_SPACE = re.compile(r"-\s+(?=\d)")
_FIX_TRAILING_COMMA = re.compile(r",(\s*[\]}])")


def _try_repair_json(s: str) -> str:
    """Apply cheap repairs for common LLM-emitted JSON malforms."""
    s = _FIX_NEG_SPACE.sub("-", s)            # "- 500" → "-500"
    s = _FIX_TRAILING_COMMA.sub(r"\1", s)      # "[1,2,]" → "[1,2]"
    return s


def _sanitize_inputs(items: list[dict]) -> list[dict]:
    """Drop items whose input_json is not valid JSON (after a cheap repair pass)."""
    clean: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = item.get("input_json")
        if not isinstance(raw, str):
            continue
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            try:
                fixed = _try_repair_json(raw)
                json.loads(fixed)
                item["input_json"] = fixed
            except json.JSONDecodeError:
                continue
        clean.append(item)
    return clean


def _extract_method_name(boilerplate: str) -> str | None:
    """Parse the first `def <name>(self` from a boilerplate string."""
    m = re.search(r"def\s+(\w+)\s*\(\s*self", boilerplate)
    return m.group(1) if m else None


def _desc(prob: Problem) -> tuple[str, str]:
    return (
        _strip_html(prob.description_md or "")[:1500],
        _strip_html(prob.constraints_md or "")[:400],
    )


def get_boilerplate(prob: Problem) -> tuple[str | None, str | None]:
    """Returns (boilerplate_python, test_harness_python). Both may be None on failure."""
    desc, constr = _desc(prob)
    try:
        data = _unwrap_json(_call(BOILERPLATE_PROMPT.format(
            title=prob.title, description=desc, constraints=constr,
        )))
        if isinstance(data, dict):
            return data.get("boilerplate_python"), data.get("test_harness_python")
    except Exception:
        pass
    return None, None


def get_inputs(prob: Problem, harness: str | None = None) -> list[dict]:
    desc, constr = _desc(prob)
    format_section = (
        CUSTOM_HARNESS_FORMAT_SECTION.format(harness=harness)
        if harness else DEFAULT_FORMAT_SECTION
    )
    raw = _call(INPUTS_PROMPT.format(
        total=70,
        title=prob.title,
        description=desc,
        constraints=constr,
        format_section=format_section,
    ))
    items: list[dict] = []
    try:
        data = _unwrap_json(raw)
        if isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    items = [x for x in v if isinstance(x, dict)]
                    break
    except json.JSONDecodeError:
        items = _extract_objects(raw)
    return _sanitize_inputs(items)


def compute_expected_outputs(
    prob: Problem, inputs: list[dict], db, harness: str | None = None
) -> list[dict]:
    """Run each input through the reference Python solution; drop cases that error."""
    ref = db.execute(
        select(Solution).where(
            Solution.problem_id == prob.id, Solution.language == "python"
        )
    ).scalar_one_or_none()

    if not ref:
        print("    (no reference solution — expected_output_json left null)", flush=True)
        return inputs  # store without expected outputs; _auto_validate handles it later

    method = prob.method_signature or "solve"
    ref_code = extract_runnable_solution(ref.code, method)
    print(f"method={method!r}", end=" ", flush=True)
    validated: list[dict] = []
    errors = 0
    first_error: str | None = None
    for item in inputs:
        try:
            args = json.loads(item["input_json"])
        except (json.JSONDecodeError, KeyError) as exc:
            if not first_error:
                first_error = f"bad input_json: {exc} — raw: {item.get('input_json', '?')[:120]}"
            errors += 1
            continue
        result = run_python(ref_code, method, args, harness=harness)
        if result["ok"]:
            item["expected_output_json"] = json.dumps(result["output"])
            item["validated"] = True
            validated.append(item)
        else:
            if not first_error:
                first_error = f"args={args!r} → {result['error'][:200]}"
            errors += 1
    if errors:
        print(f"\n    ({errors} dropped) first error: {first_error}", flush=True)
    return validated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--problem-id", type=int, default=None)
    parser.add_argument("--min-cases", type=int, default=60,
                        help="Re-process problems with fewer than this many cases")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.problem_id:
            problems = db.execute(
                select(Problem).where(Problem.id == args.problem_id)
            ).scalars().all()
        else:
            subq = (
                select(TestCase.problem_id, func.count().label("cnt"))
                .group_by(TestCase.problem_id)
                .subquery()
            )
            problems = db.execute(
                select(Problem)
                .outerjoin(subq, Problem.id == subq.c.problem_id)
                .where(Problem.description_md.isnot(None))
                .where(
                    (subq.c.cnt == None) | (subq.c.cnt < args.min_cases)  # noqa: E711
                )
                .limit(args.limit)
            ).scalars().all()

        if not problems:
            print("No problems to process (need description_md populated).")
            return

        for prob in problems:
            print(f"  [{prob.id}] {prob.title}")

            print("    boilerplate ...", end=" ", flush=True)
            boilerplate, harness = get_boilerplate(prob)
            harness_for_inputs = harness or prob.test_harness_python
            print("ok" if boilerplate else "skipped")

            print("    inputs      ...", end=" ", flush=True)
            try:
                raw_inputs = get_inputs(prob, harness=harness_for_inputs)
            except Exception as exc:
                print(f"FAILED ({exc})")
                continue
            print(f"{len(raw_inputs)} inputs received")

            print("    validating  ...", end=" ", flush=True)
            cases = compute_expected_outputs(prob, raw_inputs, db, harness=harness_for_inputs)
            print(f"{len(cases)} validated")

            if boilerplate and not prob.boilerplate_python:
                prob.boilerplate_python = boilerplate
            if harness and not prob.test_harness_python:
                prob.test_harness_python = harness
            if boilerplate and not prob.method_signature:
                extracted = _extract_method_name(boilerplate)
                if extracted:
                    prob.method_signature = extracted

            db.execute(delete(TestCase).where(TestCase.problem_id == prob.id))
            for c in cases:
                db.add(TestCase(
                    problem_id=prob.id,
                    input_json=c.get("input_json", "null"),
                    expected_output_json=c.get("expected_output_json", "null"),
                    category=c.get("category", "sample"),
                    generated_by=GENERATED_BY,
                    rationale=c.get("rationale"),
                    validated=c.get("validated", False),
                ))
            db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    main()
