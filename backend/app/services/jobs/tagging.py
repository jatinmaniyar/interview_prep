"""Tags and quality scores layered on top of normalized fields.

Three families of signals computed here:

1.  Company classification (tier + category) — coarse buckets the user trusts
    as proxies for engineering bar and brand value.
2.  Per-role quality scores:
        - role_relevance      → matches the SDE-2/Senior backend/full-stack persona
        - engineering_quality → company tier + tech stack sophistication
        - career_leverage     → does this role compound toward FAANG/L5?
3.  Behavioural signals — hiring_urgency and competition_score, kept from v1.

All scores normalize to [0, 1]. Higher is always better for the candidate
(competition_score is inverted in scoring.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from app.services.jobs._normalize import (
    BACKEND_SKILL_SIGNALS,
    DEPRIORITIZED_ROLE_FAMILIES,
    FILTERED_ROLE_FAMILIES,
    PRIORITY_ROLE_FAMILIES,
    TOLERATED_ROLE_FAMILIES,
    backend_signal_strength,
)


# ---------- company classification ----------
#
# Tiers map to brand/comp ceilings. Categories layer on top of tier and
# capture engineering-culture flavour (dev-tools, AI labs, infra, fintech).

FAANG = {
    "google", "alphabet", "amazon", "amazon-web-services",
    "meta", "facebook", "apple", "netflix", "microsoft",
}

UNICORN_HINT = {
    # generalist unicorns
    "stripe", "databricks", "canva", "figma", "notion", "discord",
    "ramp", "brex", "deel", "rippling", "gusto", "instacart", "doordash",
    # AI labs
    "openai", "anthropic", "scale-ai", "scaleai", "perplexity", "mistral",
    "cohere", "huggingface", "hugging-face", "character-ai", "characterai",
    "runway", "midjourney", "elevenlabs", "cursor", "anysphere", "supabase",
    # dev-tools / infra unicorns
    "vercel", "wiz", "snyk", "harness", "pulumi", "dbt-labs", "dbtlabs",
    "airbyte", "neon", "planetscale", "render", "fly-io", "flyio",
    "hashicorp", "confluent", "mongodb", "elastic",
    # fintech / product
    "plaid", "chime", "robinhood", "klarna", "checkout", "mercury",
}

PUBLIC_HINT = {
    "airbnb", "uber", "lyft", "shopify", "snowflake", "datadog",
    "atlassian", "salesforce", "twilio", "oracle", "ibm", "intel",
    "nvidia", "amd", "cisco", "vmware", "spotify", "block", "square",
    "paypal", "adobe", "servicenow", "workday", "okta", "cloudflare",
    "gitlab", "hashicorp", "mongodb", "confluent", "elastic",
    "pinterest", "reddit", "dropbox", "zoom", "palantir",
}

# Category buckets feed engineering_quality and career_leverage.
AI_LABS = {
    "openai", "anthropic", "google-deepmind", "deepmind",
    "scale-ai", "scaleai", "perplexity", "mistral", "cohere",
    "huggingface", "hugging-face", "character-ai", "characterai",
    "runway", "elevenlabs", "cursor", "anysphere", "x-ai", "xai",
}

DEV_TOOLS = {
    "vercel", "linear", "posthog", "supabase", "neon", "planetscale",
    "render", "fly-io", "flyio", "github", "gitlab", "hashicorp",
    "pulumi", "snyk", "harness", "airbyte", "dbt-labs", "dbtlabs",
    "replit", "stackblitz", "warp", "raycast", "arc", "cursor",
    "anysphere", "sentry", "honeycomb", "grafana", "elastic",
    "mongodb", "confluent", "redpanda", "temporal", "buildkite",
    "circleci",
}

INFRA_NATIVE = {
    "cloudflare", "fastly", "hashicorp", "datadog", "snowflake",
    "databricks", "confluent", "elastic", "redpanda", "temporal",
    "vercel", "neon", "planetscale", "render", "fly-io", "flyio",
    "tigerbeetle", "turso",
}

FINTECH_STRONG = {
    "stripe", "plaid", "ramp", "brex", "mercury", "klarna",
    "checkout", "robinhood", "chime", "block", "square", "paypal",
    "wise", "revolut",
}


def infer_tier(company_slug: str) -> str | None:
    s = (company_slug or "").lower()
    if s in FAANG: return "faang"
    if s in UNICORN_HINT: return "unicorn"
    if s in PUBLIC_HINT: return "public"
    return None


def company_categories(company_slug: str | None) -> set[str]:
    """Tags describing engineering-culture flavour. Multiple may apply."""
    s = (company_slug or "").lower()
    cats: set[str] = set()
    if s in AI_LABS: cats.add("ai_lab")
    if s in DEV_TOOLS: cats.add("dev_tools")
    if s in INFRA_NATIVE: cats.add("infra_native")
    if s in FINTECH_STRONG: cats.add("fintech")
    if s in FAANG: cats.add("faang")
    return cats


# ---------- behavioural signals ----------

def hiring_urgency(posted_at: datetime | None, repost_count: int) -> float:
    base = 0.4
    if posted_at:
        age = datetime.utcnow() - posted_at
        if age < timedelta(days=2): base = 0.95
        elif age < timedelta(days=7): base = 0.75
        elif age < timedelta(days=21): base = 0.55
        elif age < timedelta(days=45): base = 0.4
        else: base = 0.2
    if repost_count >= 2:
        base = min(1.0, base + 0.15)
    return base


_BIG_STACK_DEMAND = {"react", "typescript", "python", "go", "kubernetes", "aws"}


def competition_score(company_tier: str | None, stack: list[str], remote: str | None) -> float:
    """Higher => more crowded => worse for the applicant."""
    score = 0.5
    if company_tier == "faang": score = 0.9
    elif company_tier == "unicorn": score = 0.75
    elif company_tier == "public": score = 0.65
    if remote == "remote": score = min(1.0, score + 0.1)
    overlap = len(set(stack) & _BIG_STACK_DEMAND)
    score = min(1.0, score + 0.02 * overlap)
    return round(score, 2)


# ---------- role quality scores ----------

# Seniority alignment: how well does this role match the 3–8 YOE persona?
# Mid/senior are the bullseye; staff is a stretch (only if YOE fits);
# junior/intern/manager are far misses.
_SENIORITY_RELEVANCE = {
    "senior": 1.0,
    "mid": 0.92,
    "staff": 0.65,
    "principal": 0.30,
    "junior": 0.20,
    "manager": 0.10,
    "intern": 0.0,
    None: 0.55,  # unknown — let role family carry the weight
}

# Role-family alignment with the SDE-2/Senior backend-leaning persona.
_ROLE_FAMILY_RELEVANCE = {
    "backend":     1.0,
    "fullstack":   0.95,
    "platform":    0.92,
    "distributed": 0.95,
    "infra":       0.85,
    "api":         0.88,
    "product_eng": 0.85,
    "devops":      0.70,
    "data_eng":    0.55,
    "ml":          0.55,
    "security":    0.55,
    "frontend":    0.40,
    "mobile":      0.35,
    "other":       0.40,
    # Filtered families never reach the scorer (low_signal removes them).
    "qa": 0.0, "support": 0.0, "it_admin": 0.0, "analyst": 0.0,
    "recruiter": 0.0, "low_code": 0.0, "manager": 0.0,
}


def _yoe_alignment(yoe_min: int | None, yoe_max: int | None) -> float:
    """Penalize roles outside the 3–8 YOE window. Unknown ⇒ neutral 0.7."""
    if yoe_min is None and yoe_max is None:
        return 0.7
    low = yoe_min if yoe_min is not None else (yoe_max - 2 if yoe_max else 3)
    high = yoe_max if yoe_max is not None else low + 3
    # Sweet spot: any overlap with [3, 8] window
    if low <= 8 and high >= 3:
        # tighter overlap = higher score
        overlap_lo = max(low, 3)
        overlap_hi = min(high, 8)
        span = max(1, overlap_hi - overlap_lo + 1)
        return min(1.0, 0.7 + 0.06 * span)  # 0.76..1.0
    if low > 8:
        # 10+ years = manager territory
        return max(0.1, 1.0 - 0.08 * (low - 8))
    # high < 3 means new-grad band
    return 0.25


def role_relevance(
    role_family: str | None,
    seniority: str | None,
    yoe_min: int | None,
    yoe_max: int | None,
    is_low_signal: bool,
) -> float:
    """Primary signal for the new ranking formula. 0..1.

    Combines role-family fit (the 'what'), seniority (the 'how senior'),
    and years-of-experience window alignment. Low-signal rows collapse to 0.
    """
    if is_low_signal:
        return 0.0
    fam = _ROLE_FAMILY_RELEVANCE.get(role_family or "other", 0.3)
    sen = _SENIORITY_RELEVANCE.get(seniority, 0.55)
    yoe = _yoe_alignment(yoe_min, yoe_max)
    # Weighted average. Family is the strongest signal; seniority and yoe shape it.
    return round(0.55 * fam + 0.25 * sen + 0.20 * yoe, 4)


def engineering_quality(
    company_slug: str | None,
    company_tier: str | None,
    stack: list[str] | None,
    has_system_design: bool,
) -> float:
    """Proxy for engineering-bar / scale / architecture exposure. 0..1.

    Inputs are coarse (we have no blog scraper here), but they correlate well:
        - tier (FAANG/unicorn/public)
        - category (AI lab, dev-tools, infra-native, fintech)
        - backend skill signals (kafka, k8s, distributed, etc.)
        - explicit system-design mention in the JD
    """
    score = 0.35  # baseline floor
    tier_bump = {"faang": 0.35, "unicorn": 0.30, "public": 0.20}.get(company_tier or "", 0.0)
    score += tier_bump

    cats = company_categories(company_slug)
    if "ai_lab" in cats:       score += 0.18
    if "dev_tools" in cats:    score += 0.18
    if "infra_native" in cats: score += 0.15
    if "fintech" in cats:      score += 0.10

    stack_signal = backend_signal_strength(stack or [])
    score += 0.20 * stack_signal  # up to +0.20

    if has_system_design:
        score += 0.07

    return round(min(1.0, score), 4)


def career_leverage(
    company_slug: str | None,
    company_tier: str | None,
    role_family: str | None,
    seniority: str | None,
    stack: list[str] | None,
) -> float:
    """Estimate how much this role compounds toward FAANG / L5 / staff. 0..1.

    Heavier weight on:
      - brand value (FAANG/top unicorn)
      - role family that exposes system design + ownership
      - seniority that puts you on the L5 track
    """
    score = 0.30

    if company_tier == "faang":
        score += 0.30
    elif company_tier == "unicorn":
        score += 0.22
    elif company_tier == "public":
        score += 0.12

    cats = company_categories(company_slug)
    if cats & {"ai_lab", "dev_tools", "infra_native"}:
        score += 0.10  # high-signal engineering brand boost

    fam = role_family or "other"
    if fam in {"distributed", "platform", "infra", "backend"}:
        score += 0.15
    elif fam in {"fullstack", "api", "product_eng"}:
        score += 0.10
    elif fam in DEPRIORITIZED_ROLE_FAMILIES:
        score -= 0.05

    if seniority in {"senior", "staff"}:
        score += 0.10
    elif seniority == "mid":
        score += 0.05
    elif seniority in {"junior", "intern"}:
        score -= 0.10

    stack_signal = backend_signal_strength(stack or [])
    score += 0.10 * stack_signal

    return round(max(0.0, min(1.0, score)), 4)
