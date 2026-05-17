# Interview Prep — Phase 1

Local LeetCode-Premium-equivalent practice IDE with auto-generated test cases.

Test-case generation is driven by **Claude Code itself** (using your Claude Pro
subscription) — there is no Anthropic API key to set. The slash command
`/generate-tests` orchestrates a `testcase-generator` sub-agent per problem and
validates each proposed input by running the reference Python solution locally.

## One-time setup

### Backend

```powershell
cd e:\code\interview-prep\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m scripts.bootstrap_db
```

### Frontend

```powershell
cd e:\code\interview-prep\frontend
npm install
```

## Data ingestion (one-time, in order)

```powershell
cd e:\code\interview-prep\backend
.\.venv\Scripts\Activate.ps1

# 1. Pull LeetCode problem metadata (~3000 rows, ~5 min, rate-limited)
python -m scripts.ingest_leetcode_meta

# 2. Ingest company-tagged questions (clones the GitHub repo on first run)
python -m scripts.ingest_company_csvs

# 3. Scrape algo.monster for premium problems (start small to verify selectors)
python -m scripts.scrape_premium_problems --limit 5

# 4. Seed the System Design cookbook (problem inventory + 10 curated sections)
python -m scripts.seed_sd_cookbook
```

The SD cookbook is content-driven, not scraped. Problem inventory and
company tags live in `backend/content/sd_cookbook/problems.yaml`; the 10
reference sections live in the other YAMLs alongside it. Edit any file
and re-run `seed_sd_cookbook` (or restart the backend for non-inventory
sections, which are loaded once at startup).

## Generate test cases (Claude-Code-driven)

From the project root, with the backend `.venv` active:

```powershell
cd e:\code\interview-prep
claude
```

In the Claude Code REPL:

```
/generate-tests 5
```

That runs the slash command at [.claude/commands/generate-tests.md](.claude/commands/generate-tests.md), which:
1. Lists 5 problems with no (or <30) test cases.
2. Spawns the [testcase-generator](.claude/agents/testcase-generator.md) sub-agent per problem.
3. Saves the sub-agent's JSON proposals to `data/staging/{id}.json`.
4. Runs `python -m scripts.save_tests --problem {id} --tests-file ...` which validates each proposed input by executing the reference Python solution to compute ground-truth outputs, then persists.

Re-running is safe: problems already at ≥30 validated tests are skipped.

## Run the app

In two terminals:

```powershell
# terminal 1
cd e:\code\interview-prep\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# terminal 2
cd e:\code\interview-prep\frontend
npm run dev
```

Open http://localhost:5173.

## Phase 1 verification

1. `sqlite-utils data\interview.db "select count(*) from company_tags"` → > 5000.
2. After scraping: `select count(*) from problems where description_md is not null` → 5.
3. After `/generate-tests 5`: `select problem_id, count(*) from test_cases where validated=1 group by problem_id` → ≥25 each.
4. In browser: filter by Amazon + Medium → list populates.
5. Pick a problem, paste the algo.monster reference solution → Submit shows 100% pass.
6. Knowingly break a line → Submit shows red rows with input / expected / actual diff.

## Where things live

- `backend/app/models.py` — DB schema
- `backend/app/services/algomonster_scraper.py` — premium-problem scraper
- `backend/scripts/list_pending_tests.py` + `save_tests.py` — helpers the slash command calls
- `backend/app/runner/python_runner.py` + `cpp_runner.py` — local code execution
- `backend/app/routers/runner.py` — `/run` and `/submit`
- `frontend/src/pages/ProblemDetail.tsx` — Monaco IDE + test-result panel
- `.claude/commands/generate-tests.md` — slash-command orchestrator
- `.claude/agents/testcase-generator.md` — sub-agent contract

## Phase 2 — Job Intelligence & Referral Assistant

Aggregates jobs from public boards (Greenhouse / Lever / Ashby — no API keys),
deduplicates and tags them, scores each against a saved profile, and provides
warm-path discovery and outreach drafting via Claude Code slash commands.
**No LinkedIn scraping. No Anthropic API. No auto-messaging.**

```powershell
cd e:\code\interview-prep\backend
.\.venv\Scripts\Activate.ps1

# seed the source registry from content/job_sources.yaml, ingest, and rescore
python -m scripts.ingest_jobs --seed --rescore

# refresh later
python -m scripts.ingest_jobs --rescore

# single board
python -m scripts.ingest_jobs --source greenhouse --org stripe
```

In the app:

- `/jobs` — dashboard (dream-company openings, aggressive hirers, low-competition picks)
- `/jobs/explore` — full search + filters (tier, comp band, remote, visa, urgency, interview style…)
- `/jobs/companies` and `/jobs/companies/:slug` — company explorer + intel + warm contacts
- `/jobs/tracker` — application kanban
- `/jobs/outreach` — drafts saved by `/draft-outreach`
- `/jobs/profile` — target titles/companies/comp/stack; saving triggers a full rescore

In Claude Code (no API key):

- `/ingest-jobs [--seed] [--source X --org Y]` — pull + dedup + rescore
- `/rank-jobs [N]` — write a "why this matters" summary into the top N unscored jobs
- `/draft-outreach <job_id> [kind]` — generate recruiter_dm / referral_ask / hm_outreach / followup / thank_you
- `/find-warm-paths <company_slug> [N]` — discover plausible contacts from PUBLIC signals only (no LinkedIn)

Add more boards by editing `backend/content/job_sources.yaml` (one line per
`{source, external_org, company_name}`) and re-running `--seed`. New
providers go in `backend/app/services/jobs/providers/`.

### JobScore

`JobScore = 0.30·profile_match + 0.20·compensation + 0.15·hiring_urgency
+ 0.15·referral_probability + 0.10·company_growth + 0.05·competition_score
+ 0.05·recruiter_activity` (each component normalized to 0–1).

Stored denormalized on `job_postings.job_score` for cheap sorting; the
per-job breakdown lives in `score_breakdown_json` and is shown on the
job detail page.

## Phase 3 (later)

Mock-interview chat and STAR generator (Claude-Code-driven via additional
slash commands, like `/generate-tests`).

## Security

The runner shells out to local `python` / `g++` with no sandboxing. **Bind backend to 127.0.0.1 only** and do not expose this app on a network.
