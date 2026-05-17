---
description: Discover warm contacts at a target company from PUBLIC signals only (no LinkedIn scraping).
allowed-tools: Bash, WebFetch, WebSearch, Read, Agent
argument-hint: "<company_slug> [limit]"
---

Find plausible warm-path contacts at a target company by reading PUBLIC sources only. Save results via the API.

`$ARGUMENTS` = `<company_slug> [limit]` (default limit 10).

## Sources allowed

- Company "team" / "about" pages (often `/team`, `/about`, `/people`).
- GitHub organization members (`https://github.com/orgs/<org>/people` is gated; use `https://api.github.com/orgs/<org>/public_members` instead).
- Conference speaker lists (Strange Loop, KubeCon, PyCon, RustConf, etc.).
- Open-source contributors to the company's main repos (top contributors on `github.com/<org>/<repo>/graphs/contributors` — public).
- Public Twitter/X bios that self-identify with the company.
- Personal websites linked from those bios.

## Sources NOT allowed

- LinkedIn scraping.
- Email-pattern guessing or credential stuffing.
- Any source requiring auth / cookies / bypass of rate limits.

## Workflow

1. Get the company's `slug`, `homepage_url`, and any existing sources:

```
curl -s http://127.0.0.1:8000/api/co/<slug>
```

2. For each public source above, fetch with WebFetch / WebSearch. Pull names + roles + handles. Stop once you have ~`limit` solid candidates.

3. For each candidate, rank by `kind`:
   - `recruiter`: title contains "recruit", "talent", "people ops"
   - `hiring_manager`: "engineering manager", "director of engineering", "head of <team>"
   - `engineer`: SWE / staff / principal engineer
   - `recent_joiner`: joined < 6 months ago (only if explicitly stated)
   - `ex_employee`: bio says "ex-<company>" or "previously at <company>"

   `relevance_score` (0–1): start at 0.5, +0.2 for hiring_manager, +0.15 for stack overlap with user's profile (fetch `/api/profile`), +0.1 for being a recent joiner, −0.1 if role is unrelated (sales/marketing/legal).

4. Save each contact:

```
curl -s -X POST http://127.0.0.1:8000/api/warm-contacts \
  -H "Content-Type: application/json" \
  -d '{"company_id":<id>, "name":"<n>", "role":"<r>", "kind":"<k>", "github_handle":"<gh>", "twitter_handle":"<tw>", "website":"<url>", "source_url":"<where you found them>", "relevance_score":<0..1>}'
```

5. Print a tight summary: how many added, breakdown by kind, top 3 by relevance.

## Rules

- **Never** invent emails, DM anyone, or fabricate handles.
- Always set `source_url` to where the candidate's public profile/page was found, so the user can verify.
- Skip candidates whose public role isn't obviously engineering / recruiting / leadership.
- Honor robots.txt and rate limits — one fetch every couple of seconds.
