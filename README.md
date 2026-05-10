# Interview Prep — Phase 1

Local LeetCode-Premium-equivalent practice IDE with auto-generated test cases.

## One-time setup

### Backend

```powershell
cd e:\code\interview-prep\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env to add ANTHROPIC_API_KEY
python -m scripts.bootstrap_db
```

### Frontend

```powershell
cd e:\code\interview-prep\frontend
npm install
```

## Data ingestion (one-time, in order)

```powershell
# 1. Pull LeetCode problem metadata (~3000 rows, ~5 min, rate-limited 1 req/sec)
cd e:\code\interview-prep\backend
.\.venv\Scripts\Activate.ps1
python -m scripts.ingest_leetcode_meta

# 2. Ingest company-tagged questions (clones the GitHub repo on first run)
python -m scripts.ingest_company_csvs

# 3. Scrape algo.monster for premium problems (start with --limit 5 to verify)
python -m scripts.scrape_premium_problems --limit 5

# 4. Generate test cases for the scraped problems
python -m scripts.generate_test_cases --limit 5
```

`MAX_DAILY_SPEND_USD` in `.env` caps step 4. The script exits when the cap is hit.

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
2. After step 3 of ingestion: `select count(*) from problems where description_md is not null` → 5.
3. After step 4: `select count(*) from test_cases where validated=1 group by problem_id` → ≥30 each.
4. In browser: filter by Amazon + Medium → list populates.
5. Pick a problem, paste the algo.monster reference solution → Submit shows 100% pass.
6. Knowingly break a line → Submit shows red rows with input / expected / actual diff.

## Where things live

- `backend/app/models.py` — all DB schema
- `backend/app/services/algomonster_scraper.py` — premium-problem scraper
- `backend/app/services/claude_client.py` — Anthropic SDK wrapper with caching + spend log
- `backend/scripts/generate_test_cases.py` — sequential per-problem test gen (the cost-sensitive one)
- `backend/app/runner/python_runner.py` + `cpp_runner.py` — local code execution
- `backend/app/routers/runner.py` — `/run` and `/submit`
- `frontend/src/pages/ProblemDetail.tsx` — Monaco IDE + test panel

## Phase 2 (later)

Jobs (JSearch + Adzuna), system design bank, mock interview chat, STAR generator. Schema and Claude client are already in place.

## Security

The runner shells out to local `python` / `g++` with no sandboxing. **Bind backend to 127.0.0.1 only** and do not expose this app on a network.
