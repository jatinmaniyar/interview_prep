---
description: Draft personalized outreach messages for a job. Usage:/draft-outreach <job_id> [kind]
allowed-tools: Bash, Read, Write
argument-hint: "<job_id> [recruiter_dm|referral_ask|hm_outreach|followup|thank_you]"
---

Generate a personalized outreach draft for a specific job and persist it via the API.

`$ARGUMENTS` should be `<job_id> [kind]`. If `kind` omitted, default `recruiter_dm`.

## Workflow

1. Fetch context in one shot:

```
curl -s http://127.0.0.1:8000/api/jobs/<job_id>
curl -s http://127.0.0.1:8000/api/profile
```

(Backend must be running. If `curl` fails, tell the user to start `uvicorn app.main:app --reload` from `backend/` and stop.)

2. Compose the draft. Hard rules:
   - **Concise.** ≤120 words for DMs/emails, ≤80 for thank-yous.
   - **No hype phrases.** No "I'm passionate about", "thrilled to", "rockstar", etc.
   - **One specific hook tied to the company.** Pull from the job description (product line, stack overlap, scale claim) or a known signal — not generic praise.
   - **One specific credential from the user's resume that maps to the role.**
   - **Clear ask.** Referral, 15-min chat, or screen — pick one.
   - Plain text. No markdown headings inside the body.

3. Save it:

```
curl -s -X POST http://127.0.0.1:8000/api/outreach \
  -H "Content-Type: application/json" \
  -d '{"job_id":"<job_id>","kind":"<kind>","subject":"<subject>","body_md":"<body>"}'
```

Tell the user the draft is now visible at /jobs/outreach and on the job detail page.

## Kinds

- `recruiter_dm`: short LinkedIn/email DM to a recruiter. Include role + one credential + ask for a call.
- `referral_ask`: directed at a warm contact (or general employee). Acknowledge it's a cold ask; reference one specific reason this contact in particular is a good bridge.
- `hm_outreach`: longer (≤180 words), aimed at hiring manager. Explain the role-level fit with two concrete examples.
- `followup`: 4–7 days after applying. Reference application date, restate one differentiator, request status or short call.
- `thank_you`: post-interview. Reference one specific topic discussed; one sentence reaffirming interest.

## Rules

- Never auto-send. Drafts only.
- If the job has no `company` joined or the profile is empty, abort with a clear message about what's missing.
- Do not invent contact details. The draft body should NOT include "Dear <name>" unless a contact_id is also passed — leave as "Hi there," otherwise.
