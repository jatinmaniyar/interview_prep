---
description: Pull fresh jobs from configured Greenhouse/Lever/Ashby boards, then rescore.
allowed-tools: Bash
argument-hint: "[--seed] [--source <name> --org <token>]"
---

Ingest job postings from all enabled providers and rescore. Optional args are forwarded to the script.

Run from repo root:

```
cd backend && python -m scripts.ingest_jobs $ARGUMENTS
```

Notes:
- First time? Run `python -m scripts.ingest_jobs --seed` to load `backend/content/job_sources.yaml` into the registry, then ingest.
- The script prints a JSON summary per source. Surface the headline numbers (total new, total deactivated, any errors) to the user. Skip the rest.
- If any source returns a 4xx, check that the board token is correct (boards-api.greenhouse.io/v1/boards/{org}/jobs should respond).
