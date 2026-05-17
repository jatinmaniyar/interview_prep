---
description: Generate validated test cases for the next N problems that need them. Usage:/generate-tests [limit] (default 5)
allowed-tools: Bash, Read, Write, Agent
argument-hint: "[limit]"
---

You will generate validated test cases for the next batch of LeetCode problems in this project's database. Work sequentially — one problem at a time — to keep memory bounded.

## Inputs

User-provided argument: `$ARGUMENTS` (a number; default 5 if empty).

## Workflow

### 1. List pending problems

Run from the repo root:

```
python -m scripts.list_pending_tests --limit ${ARGUMENTS:-5}
```

(working dir is `backend/` — `cd backend` first if needed.)

Parse the JSON array. If empty, report "no pending problems" and stop.

### 2. For each problem in the list, in order:

a. **Spawn the `testcase-generator` sub-agent** with a prompt containing:
   - `id`, `title`, `description_md`, `constraints_md`
   - The Python `ref_code`
   - The `method` name

   The sub-agent returns ONLY a JSON array of `{input, category, rationale}` (no expected outputs, no markdown fences).

b. **Save the sub-agent's JSON to a temp file** under `data/staging/{id}.json` (create the dir if missing — `mkdir -p data/staging`).

c. **Run the validator/saver** which executes the reference solution against each input to compute ground-truth outputs and persists validated rows:

   ```
   python -m scripts.save_tests --problem {id} --tests-file ../data/staging/{id}.json --replace
   ```

   Parse the returned JSON (`{ok, saved, invalid, per_category}`) and record the result.

d. If `saved < 25`, retry once: re-spawn the sub-agent asking specifically for more `edge` and `adversarial` cases, append-and-re-run with `--replace` removed (no, just re-run without `--replace` so prior validated rows stay). Skip retry if first run failed catastrophically.

### 3. Summary

Print a tight summary: per-problem `saved` counts, total saved, total invalid. List any problems that ended below 25 validated cases as "needs follow-up."

## Rules

- **Sequential, not parallel.** One sub-agent at a time. This keeps the main agent's context bounded and makes a stuck problem easy to spot.
- **Do not** edit DB rows directly — always go through `save_tests.py` so validation runs.
- **Do not** invent expected outputs in the main agent. Only the validator computes them.
- If a sub-agent returns invalid JSON, capture the raw output to `data/staging/{id}.error.txt` and skip the problem; report it in the summary.
- The Python venv must be active before running scripts. If `python -m scripts.list_pending_tests` fails with `ModuleNotFoundError`, surface a one-line note about activating `.venv` and stop.
