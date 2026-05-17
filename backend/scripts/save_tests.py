"""Validate + save sub-agent-generated test inputs for one problem.

Reads a JSON array of {input, category, rationale} from --tests-file (or stdin),
runs the reference Python solution against each input to compute the ground-truth
expected output, and persists validated rows to test_cases.

Inputs that crash or time out under the reference solution are dropped (those are
sub-agent mistakes — the orchestrator doesn't need to know).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution, TestCase  # noqa: E402
from app.runner.python_runner import run_python  # noqa: E402

VALID_CATEGORIES = {"sample", "edge", "stress", "adversarial"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", type=int, required=True)
    ap.add_argument(
        "--tests-file",
        type=str,
        default=None,
        help="Path to JSON file with the proposals. If omitted, read stdin.",
    )
    ap.add_argument("--replace", action="store_true", help="Delete existing tests first")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    if args.tests_file:
        raw = Path(args.tests_file).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    try:
        proposals = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid json: {e}"}))
        sys.exit(1)

    db = SessionLocal()
    try:
        problem = db.get(Problem, args.problem)
        if not problem:
            print(json.dumps({"ok": False, "error": "problem not found"}))
            sys.exit(1)
        ref = db.execute(
            select(Solution).where(
                Solution.problem_id == args.problem, Solution.language == "python"
            )
        ).scalar_one_or_none()
        if not ref:
            print(json.dumps({"ok": False, "error": "no python ref solution"}))
            sys.exit(1)

        method = problem.method_signature or "solve"

        if args.replace:
            db.execute(delete(TestCase).where(TestCase.problem_id == args.problem))

        saved = 0
        invalid = 0
        per_category = {c: 0 for c in VALID_CATEGORIES}
        for prop in proposals:
            args_in = prop.get("input")
            category = prop.get("category", "edge")
            rationale = prop.get("rationale", "")
            if args_in is None or category not in VALID_CATEGORIES:
                invalid += 1
                continue
            result = run_python(ref.code, method, args_in, timeout_s=args.timeout)
            if not result["ok"]:
                invalid += 1
                continue
            db.add(
                TestCase(
                    problem_id=args.problem,
                    input_json=json.dumps(args_in),
                    expected_output_json=json.dumps(result["output"]),
                    category=category,
                    generated_by="claude-code-subagent",
                    rationale=rationale,
                    validated=True,
                )
            )
            saved += 1
            per_category[category] += 1
        db.commit()

        print(
            json.dumps(
                {
                    "ok": True,
                    "problem": args.problem,
                    "title": problem.title,
                    "saved": saved,
                    "invalid": invalid,
                    "per_category": per_category,
                }
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
