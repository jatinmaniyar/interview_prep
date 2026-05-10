"""Generate validated test cases for premium problems.

Strategy:
  1. For each problem, call Claude with a cached system prompt + the problem
     description + the algo.monster Python reference solution. Claude returns a
     JSON array of test INPUTS only (no expected outputs).
  2. Locally execute the reference solution on each input to compute the ground
     truth expected output. Skip inputs that crash the reference solution
     (Claude proposed something invalid).
  3. Persist as validated test cases.

Sequential by design — keeps the prompt-cache warm and makes spend predictable.
Daily $ cap enforced via app.services.claude_client.check_budget().
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution, TestCase  # noqa: E402
from app.runner.python_runner import run_python  # noqa: E402
from app.services.claude_client import message  # noqa: E402

SYSTEM_PROMPT = """You are a test-case author for LeetCode-style coding problems. Your output drives an automated grader.

You will be given a problem description, a reference Python solution, and a method name. You must return ONLY a JSON array (no prose, no markdown fences) of objects:

[{"input": [<args matching the method signature>], "category": "sample|edge|stress|adversarial", "rationale": "<<=80 chars>"}]

Quotas (total 30-40 cases):
- sample (3-5): canonical examples from the problem statement.
- edge (10-15): empty/single, min/max constraints, all-same, all-distinct, sorted, reverse-sorted, boundary off-by-ones, negatives where applicable.
- stress (5-10): inputs at the constraint upper bound to catch slow solutions.
- adversarial (5-10): inputs designed to break common wrong approaches for THIS problem class.

Rules:
- Do NOT include expected_output. The orchestrator computes it.
- Respect stated input bounds. Do not invent constraints.
- Output raw JSON only, no markdown fences.
- For trees/lists, use standard LeetCode array serialization.
- For multi-arg methods, "input" is a list in argument order.
- Keep each input under 5KB. Stress cases may use programmatic patterns expanded literally."""

USER_TEMPLATE = """Problem #{id}: {title}

## Description
{description}

## Constraints
{constraints}

## Reference Python solution
```python
{ref_code}
```

Method to call: `Solution().{method}(...)`

Return the JSON array of test inputs now."""


def parse_json_array(raw: str) -> list[dict]:
    s = raw.strip()
    if s.startswith("```"):
        # strip code fences if Claude emitted them despite instructions
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
        # find the JSON content between fences if still wrapped
    # find first '[' and last ']'
    a = s.find("[")
    b = s.rfind("]")
    if a == -1 or b == -1:
        raise ValueError(f"No JSON array found in response: {s[:200]}")
    return json.loads(s[a : b + 1])


def already_done(db, pid: int, min_count: int) -> bool:
    n = db.execute(
        select(func.count())
        .select_from(TestCase)
        .where(TestCase.problem_id == pid, TestCase.validated == True)  # noqa: E712
    ).scalar_one()
    return n >= min_count


def generate_for_problem(db, problem: Problem, ref: Solution, force: bool, min_count: int) -> dict:
    if not force and already_done(db, problem.id, min_count):
        return {"status": "skipped", "reason": "cached", "passed": 0}

    method = problem.method_signature or "solve"
    user = USER_TEMPLATE.format(
        id=problem.id,
        title=problem.title,
        description=problem.description_md or "(no description)",
        constraints=problem.constraints_md or "(none stated)",
        ref_code=ref.code,
        method=method,
    )

    # Cached system prompt (constant across problems => cache hit after first call)
    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    text, cost = message(
        component="testcase-gen",
        system_blocks=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=8192,
        note=f"problem={problem.id}",
    )

    try:
        proposals = parse_json_array(text)
    except Exception as e:
        return {"status": "error", "reason": f"bad json: {e}", "cost": cost}

    # Validate by running ref solution
    if force:
        db.execute(delete(TestCase).where(TestCase.problem_id == problem.id))

    saved = 0
    invalid = 0
    for prop in proposals:
        args = prop.get("input")
        category = prop.get("category", "edge")
        rationale = prop.get("rationale", "")
        if args is None or category not in {"sample", "edge", "stress", "adversarial"}:
            invalid += 1
            continue
        result = run_python(ref.code, method, args, timeout_s=10.0)
        if not result["ok"]:
            invalid += 1
            continue
        tc = TestCase(
            problem_id=problem.id,
            input_json=json.dumps(args),
            expected_output_json=json.dumps(result["output"]),
            category=category,
            generated_by="claude-opus-4-7",
            rationale=rationale,
            validated=True,
        )
        db.add(tc)
        saved += 1
    db.commit()

    return {
        "status": "ok",
        "proposed": len(proposals),
        "saved": saved,
        "invalid": invalid,
        "cost": cost,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", type=str, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--min-count", type=int, default=30)
    ap.add_argument("--sleep", type=float, default=2.0, help="Seconds between problems")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.ids:
            ids = [int(x) for x in args.ids.split(",")]
        else:
            q = select(Problem.id).where(
                Problem.description_md.is_not(None), Problem.description_md != ""
            )
            if args.limit:
                q = q.limit(args.limit)
            ids = [r[0] for r in db.execute(q).all()]

        total_cost = 0.0
        for i, pid in enumerate(ids, 1):
            problem = db.get(Problem, pid)
            if not problem:
                continue
            ref = db.execute(
                select(Solution).where(
                    Solution.problem_id == pid, Solution.language == "python"
                )
            ).scalar_one_or_none()
            if not ref:
                print(f"  [{i}/{len(ids)}] #{pid}: no python ref solution, skipping")
                continue
            try:
                outcome = generate_for_problem(db, problem, ref, args.force, args.min_count)
            except Exception as e:
                print(f"  [{i}/{len(ids)}] #{pid}: {type(e).__name__}: {e}")
                continue
            total_cost += outcome.get("cost", 0.0)
            print(f"  [{i}/{len(ids)}] #{pid} {problem.title}: {outcome}")
            time.sleep(args.sleep)

        print(f"Total estimated cost: ${total_cost:.4f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
