---
description: Generate one-paragraph "why this matters" summaries for the top N unscored jobs.
allowed-tools: Bash, Read, Write
argument-hint: "[limit] (default 10)"
---

Generate concise "why this role fits the user" summaries for the top scoring jobs that don't yet have one. Writes the result into `JobPosting.ai_summary_md` via a small SQL update — no Anthropic API.

## Workflow

1. Read the user's profile and the top N candidate jobs in one shot:

```
cd backend && python -m scripts.jobs_export_for_ranking --limit ${ARGUMENTS:-10}
```

(If that script doesn't exist yet, create it — it should print JSON:
`{"profile": {...}, "jobs": [{"id", "title", "company_name", "location", "remote", "salary_max", "salary_currency", "stack", "seniority", "score_breakdown"}]}`.
Only include jobs where `ai_summary_md IS NULL` and `is_active`.)

2. For each job in the returned list, compose a 2–3 sentence summary in your head, focused on:
   - the highest-weighted positive components from `score_breakdown`
   - any obvious mismatch worth calling out (e.g. salary below target, no visa)
   - one concrete reason to apply tied to the user's stack or target companies

   Keep it factual. No hype. No emojis. No second-person ("you") — write as third-person notes the user will skim.

3. Persist via:

```
python -m scripts.jobs_set_summary --id "<job_id>" --md "<one-paragraph summary>"
```

(Create this script if missing — it just runs `UPDATE job_postings SET ai_summary_md=? WHERE id=?`.)

## Rules

- Sequential, one job at a time. Don't batch multiple summaries into a single update call.
- If profile is missing target_titles/target_companies/stack, stop and tell the user to fill out `/jobs/profile` first.
- Do NOT call the Anthropic API. All reasoning happens in this main agent, then a single SQL write per job.
