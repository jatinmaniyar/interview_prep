"""Normalization helpers: title/seniority/role/yoe/location/salary/stack.

Heuristics only. Keep it cheap; no LLM calls here.

This module is the inference foundation for the Job Intelligence pipeline.
Everything downstream (scoring, filtering, AI summaries) relies on
role_family / seniority / yoe / low_signal being set correctly here.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

from selectolax.parser import HTMLParser

# ---------- seniority ----------
#
# Order matters: first match wins. "Senior staff" should hit staff, not senior.
# "Software Engineer II" → mid, "III" → senior, "IV" → staff.
# "Member of Technical Staff" at startups → senior (the default L5-ish MTS bar).
# "Founding Engineer" → senior unless YOE explicitly says otherwise.

_SENIORITY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\b(intern|internship|co-?op|apprentice|trainee)\b", re.I)),
    ("principal", re.compile(r"\b(principal|distinguished|fellow|architect\s+v|chief\s+engineer)\b", re.I)),
    ("staff", re.compile(
        r"\b("
        r"staff\s+(?:software\s+)?(?:engineer|swe)|"
        r"sde[\s-]*3|sde[\s-]*iii|"
        r"software\s+engineer\s+iv|swe\s+iv|"
        r"l[6-7]|e[6-7]|ic[5-6]"
        r")\b", re.I)),
    ("manager", re.compile(
        r"\b("
        r"engineering\s+manager|eng\s+manager|"
        r"director(\s+of)?|head\s+of|vp\s+of|"
        r"team\s+lead(?!\s+engineer)"
        r")\b", re.I)),
    ("senior", re.compile(
        r"\b("
        r"senior(?!\s+manager)|sr\.?|"
        r"lead\s+(?:software\s+)?engineer|"
        r"member\s+of\s+technical\s+staff|mts|"
        r"founding\s+engineer|"
        r"l5|e5|ic4|"
        r"sde[\s-]*2|sde[\s-]*ii|"
        r"software\s+engineer\s+iii|swe\s+iii|"
        r"software\s+development\s+engineer\s+iii"
        r")\b", re.I)),
    ("mid", re.compile(
        r"\b("
        r"mid[\s-]?level|mid[\s-]?senior|"
        r"l4|e4|ic3|"
        r"software\s+engineer\s+ii|swe\s+ii|"
        r"software\s+development\s+engineer\s+ii|"
        r"sde[\s-]*ii?(?![iI])"  # SDE II but not SDE III handled above
        r")\b", re.I)),
    ("junior", re.compile(
        r"\b("
        r"junior|jr\.?|"
        r"new\s+grad|entry[\s-]?level|early[\s-]?career|"
        r"graduate\s+(?:software\s+)?engineer|"
        r"l3|e3|ic2|"
        r"software\s+engineer\s+i|swe\s+i|"
        r"sde[\s-]*1|sde[\s-]*i(?![iI])"
        r")\b", re.I)),
]


def infer_seniority(title: str, description: str | None = None, yoe_min: int | None = None) -> str | None:
    """Title is primary signal; description supplements; yoe_min overrides when title is bare 'Software Engineer'."""
    blob = (title or "").strip()
    if not blob:
        return None
    for label, pat in _SENIORITY_PATTERNS:
        if pat.search(blob):
            return label
    # Fallback: scan a short description prefix for explicit level markers
    if description:
        desc_head = description[:1500]
        for label, pat in _SENIORITY_PATTERNS:
            if pat.search(desc_head):
                return label
    # Last resort: if the role is bare "Software Engineer" and we have YOE, map by years
    if yoe_min is not None:
        if yoe_min >= 8:
            return "staff"
        if yoe_min >= 5:
            return "senior"
        if yoe_min >= 3:
            return "mid"
        if yoe_min >= 1:
            return "junior"
    return None


# ---------- years-of-experience ----------
#
# Matches "3+ years", "3-5 years", "5 to 8 years", "at least 4 years",
# "minimum of 5 years", "5+ yrs", "5 years of experience".
_YOE_PATTERNS = [
    re.compile(r"\b(?P<low>\d{1,2})\s*[-–to]+\s*(?P<high>\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I),
    re.compile(r"\b(?:minimum\s+of\s+|at\s+least\s+|\+\s*)?(?P<low>\d{1,2})\s*\+\s*(?:years?|yrs?)\b", re.I),
    re.compile(r"\b(?:minimum\s+of\s+|at\s+least\s+)(?P<low>\d{1,2})\s*(?:years?|yrs?)\b", re.I),
    re.compile(r"\b(?P<low>\d{1,2})\s*(?:years?|yrs?)\s+of\s+(?:professional\s+|industry\s+)?experience\b", re.I),
]


def infer_yoe(description: str | None) -> tuple[int | None, int | None]:
    """Return (yoe_min, yoe_max) parsed from job description. Best effort."""
    if not description:
        return None, None
    # Look in the first 4000 chars; requirements are usually near the top.
    head = description[:4000]
    best_low: int | None = None
    best_high: int | None = None
    for pat in _YOE_PATTERNS:
        m = pat.search(head)
        if not m:
            continue
        try:
            low = int(m.group("low"))
        except (ValueError, IndexError):
            continue
        high = None
        try:
            high = int(m.group("high"))
        except (ValueError, IndexError):
            pass
        # sanity: reject absurd parses (e.g. dates like "2024 years")
        if low > 20 or (high and high > 30):
            continue
        if best_low is None or low < best_low:
            best_low = low
        if high and (best_high is None or high > best_high):
            best_high = high
    return best_low, best_high


# ---------- role family ----------
#
# Maps a job title (and description as backup) to a coarse engineering bucket
# so we can prioritise backend/full-stack/platform and downrank QA/support/etc.

_ROLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    # NON-engineering / low signal first (must run before generic engineer matches)
    ("qa",        re.compile(r"\b(qa\s+engineer|quality\s+(assurance|engineer)|test\s+engineer|sdet|manual\s+test(er|ing)|automation\s+test)\b", re.I)),
    ("support",   re.compile(r"\b(support\s+engineer|technical\s+support|customer\s+(success|support)|implementation\s+engineer|solutions?\s+engineer|sales\s+engineer)\b", re.I)),
    ("it_admin",  re.compile(r"\b(it\s+(admin|support|operations?)|sysadmin|system\s+admin(istrator)?|desktop\s+support|helpdesk)\b", re.I)),
    ("analyst",   re.compile(r"\b(data\s+analyst|business\s+analyst|reporting\s+analyst|bi\s+analyst|financial\s+analyst|product\s+analyst)\b", re.I)),
    ("recruiter", re.compile(r"\b(recruiter|talent\s+(acquisition|partner|sourcer)|sourcing\s+specialist)\b", re.I)),
    ("low_code",  re.compile(r"\b(low[\s-]?code|no[\s-]?code|salesforce\s+(admin|developer)|servicenow|workday|sap\s+(consultant|developer)|sharepoint)\b", re.I)),
    ("manager",   re.compile(r"\b(engineering\s+manager|eng\s+manager|director|head\s+of|vp\s+of)\b", re.I)),
    # Engineering specialisations (most specific first)
    ("distributed", re.compile(r"\b(distributed\s+systems?|distributed\s+computing|consensus|raft|paxos|stream\s+processing\s+engineer)\b", re.I)),
    ("infra",     re.compile(r"\b(infrastructure\s+engineer|infra\s+engineer|sre|site\s+reliability|reliability\s+engineer|production\s+engineer|systems\s+engineer)\b", re.I)),
    ("platform",  re.compile(r"\b(platform\s+engineer|developer\s+platform|internal\s+platform|cloud\s+platform|build\s+platform)\b", re.I)),
    ("devops",    re.compile(r"\b(devops|cloud\s+engineer|kubernetes\s+engineer|deployment\s+engineer)\b", re.I)),
    ("data_eng",  re.compile(r"\b(data\s+engineer|analytics\s+engineer|data\s+platform|etl\s+engineer)\b", re.I)),
    ("ml",        re.compile(r"\b(machine\s+learning\s+engineer|ml\s+engineer|mle|ai\s+engineer|research\s+engineer|applied\s+(ai|ml)\s+engineer)\b", re.I)),
    ("security",  re.compile(r"\b(security\s+engineer|appsec|application\s+security|product\s+security|infosec)\b", re.I)),
    ("mobile",    re.compile(r"\b(ios|android|mobile)\s+(engineer|developer)\b", re.I)),
    ("frontend",  re.compile(r"\b(frontend|front[\s-]?end|ui|ux\s+engineer|web\s+(developer|engineer))\b", re.I)),
    ("api",       re.compile(r"\b(api\s+(engineer|developer)|integrations?\s+engineer)\b", re.I)),
    ("backend",   re.compile(r"\b(back[\s-]?end|server[\s-]?side|services\s+engineer)\b.*\bengineer\b", re.I)),
    ("backend",   re.compile(r"\bengineer\b.*\b(back[\s-]?end|server[\s-]?side|services)\b", re.I)),
    ("fullstack", re.compile(r"\b(full[\s-]?stack|full\s+stack)\s+(engineer|developer)\b", re.I)),
    ("product_eng", re.compile(r"\b(product\s+engineer|founding\s+engineer|member\s+of\s+technical\s+staff|mts)\b", re.I)),
    # Generic catch-alls (least specific last)
    ("backend",   re.compile(r"\b(software\s+(development\s+)?engineer|swe|sde)\b", re.I)),  # default SWEs -> backend bucket
]


# Role buckets we ACTIVELY want; everything else is deprioritized or filtered.
PRIORITY_ROLE_FAMILIES = {
    "backend", "fullstack", "platform", "infra", "distributed",
    "api", "product_eng", "devops",
}
TOLERATED_ROLE_FAMILIES = {"data_eng", "ml", "security", "frontend"}  # show but lower-ranked
DEPRIORITIZED_ROLE_FAMILIES = {"mobile"}
FILTERED_ROLE_FAMILIES = {"qa", "support", "it_admin", "analyst", "recruiter", "low_code", "manager"}


def infer_role_family(title: str, description: str | None = None) -> str:
    """Return one of: backend, fullstack, platform, infra, distributed, api,
    product_eng, devops, data_eng, ml, security, frontend, mobile,
    qa, support, it_admin, analyst, recruiter, low_code, manager, other.
    """
    t = (title or "").strip()
    if not t:
        return "other"
    for label, pat in _ROLE_PATTERNS:
        if pat.search(t):
            return label
    # Title was inconclusive; try description prefix
    if description:
        head = description[:2000]
        for label, pat in _ROLE_PATTERNS:
            if pat.search(head):
                return label
    return "other"


# ---------- low-signal / spam filter ----------
#
# Drops staffing-agency reposts, consultancy spam, and roles that are
# clearly outside the target persona regardless of title.

_LOW_SIGNAL_TITLE = re.compile(
    r"\b("
    r"staffing|consultant\s+\(|c2c|w2\s+only|"
    r"recruiter|talent\s+(acquisition|partner)|"
    r"intern(ship)?|co-?op|"
    r"manual\s+test|quality\s+assurance|sdet|"
    r"support\s+engineer|technical\s+support|"
    r"it\s+admin|sysadmin|desktop\s+support|"
    r"data\s+entry|analyst\s+i\b"
    r")\b",
    re.I,
)

_LOW_SIGNAL_COMPANY_HINT = re.compile(
    r"\b("
    r"staffing|consultants?|consulting\s+services|solutions?\s+(inc|llc|pvt)|"
    r"tek\s*systems|cognizant\s+(staffing|consulting)|"
    r"vendor|outsourc(ing|ed)"
    r")\b",
    re.I,
)

_LOW_SIGNAL_DESC = re.compile(
    r"\b("
    r"c2c\s+only|corp\s+to\s+corp|"
    r"w2\s+only|on\s+w2|"
    r"must\s+have\s+own\s+visa|"
    r"\b10\s*\+\s*years.*\bmanagement\s+experience"  # senior manager roles
    r")\b",
    re.I,
)


def is_low_signal(title: str, company_name: str | None, description: str | None, role_family: str) -> bool:
    """True ⇒ skip ranking, hide by default. Reversible via filter override."""
    if role_family in FILTERED_ROLE_FAMILIES:
        return True
    if _LOW_SIGNAL_TITLE.search(title or ""):
        return True
    if company_name and _LOW_SIGNAL_COMPANY_HINT.search(company_name):
        return True
    if description and _LOW_SIGNAL_DESC.search(description[:3000]):
        return True
    return False


# ---------- remote / location ----------

_REMOTE_RE = re.compile(r"\b(remote|work\s*from\s*home|wfh|anywhere|distributed)\b", re.I)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)


def infer_remote(location: str | None, description: str | None, workplace: str | None = None) -> str | None:
    blob = " ".join(x for x in (workplace or "", location or "", (description or "")[:1000]) if x)
    if not blob:
        return None
    if _REMOTE_RE.search(blob) and not _HYBRID_RE.search(blob):
        return "remote"
    if _HYBRID_RE.search(blob):
        return "hybrid"
    if location:
        return "onsite"
    return None


_COUNTRY_HINTS = {
    "united states": "US", "usa": "US", " us": "US", "united kingdom": "UK", "uk": "UK",
    "canada": "CA", "germany": "DE", "france": "FR", "india": "IN", "ireland": "IE",
    "netherlands": "NL", "singapore": "SG", "australia": "AU", "japan": "JP",
    "spain": "ES", "portugal": "PT", "israel": "IL", "switzerland": "CH",
}


def infer_country(location: str | None) -> str | None:
    if not location:
        return None
    low = location.lower()
    for k, v in _COUNTRY_HINTS.items():
        if k in low:
            return v
    if re.search(r",\s*[A-Z]{2}\b", location):
        return "US"
    return None


# ---------- salary ----------

_SALARY_RE = re.compile(
    r"(?P<cur>[$€£₹])?\s*(?P<low>\d{2,3})\s*(?P<lu>k|,?\d{3})?\s*[-–to]+\s*(?P<cur2>[$€£₹])?\s*(?P<high>\d{2,3})\s*(?P<hu>k|,?\d{3})?",
    re.I,
)
_CUR_MAP = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}


def parse_salary_range(text: str | None) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None
    m = _SALARY_RE.search(text)
    if not m:
        return None, None, None
    def to_int(num: str, unit: str | None) -> int | None:
        try:
            n = int(num)
        except ValueError:
            return None
        if unit and unit.lower().startswith("k"):
            return n * 1000
        if unit and unit.startswith(","):
            return int(num + unit.replace(",", ""))
        if n < 1000:
            return n * 1000
        return n
    low = to_int(m.group("low"), m.group("lu"))
    high = to_int(m.group("high"), m.group("hu"))
    cur = _CUR_MAP.get(m.group("cur") or m.group("cur2") or "", None)
    if low and high and low > high:
        low, high = high, low
    return low, high, cur


def salary_band(salary_max: int | None, currency: str | None) -> str | None:
    if not salary_max:
        return None
    if currency in (None, "USD"):
        if salary_max >= 400_000: return "top"
        if salary_max >= 250_000: return "high"
        if salary_max >= 150_000: return "mid"
        return "low"
    if currency == "INR":
        if salary_max >= 8_000_000: return "top"
        if salary_max >= 4_000_000: return "high"
        if salary_max >= 2_000_000: return "mid"
        return "low"
    if currency in ("EUR", "GBP"):
        if salary_max >= 200_000: return "top"
        if salary_max >= 130_000: return "high"
        if salary_max >= 80_000: return "mid"
        return "low"
    return None


# ---------- stack / skills ----------
#
# Expanded with backend/distributed/cloud signals the user explicitly cares about.
# Order matters only for display (first-match listing keeps it deterministic).

_STACK_KEYWORDS = [
    # languages
    "python", "typescript", "javascript", "java", "kotlin", "scala", "go", "golang",
    "rust", "c++", "c#", ".net", "ruby", "rails", "php", "swift", "objective-c",
    # web/frontend frameworks
    "react", "next.js", "vue", "angular", "svelte",
    # backend frameworks
    "node", "django", "fastapi", "flask", "spring boot", "spring", "express", "nestjs",
    # data stores
    "postgres", "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
    "elasticsearch", "opensearch", "clickhouse",
    # streaming / messaging
    "kafka", "rabbitmq", "pulsar", "kinesis", "nats",
    # data platform
    "snowflake", "bigquery", "spark", "hadoop", "airflow", "dbt", "flink",
    # cloud / infra
    "aws", "gcp", "azure", "kubernetes", "k8s", "docker", "terraform", "helm",
    "istio", "envoy", "consul", "vault",
    # APIs / protocols
    "graphql", "grpc", "rest", "protobuf", "websocket",
    # architecture patterns
    "microservices", "event-driven", "event sourcing", "cqrs", "service mesh",
    "distributed systems", "scalability", "caching", "ci/cd", "observability",
    "prometheus", "grafana", "opentelemetry", "datadog",
    # ml
    "ml", "machine learning", "llm", "pytorch", "tensorflow", "cuda",
]

# Skills that signal a strong backend/distributed-systems role.
BACKEND_SKILL_SIGNALS = {
    "kafka", "redis", "postgresql", "postgres", "cassandra", "dynamodb",
    "kubernetes", "k8s", "spring boot", "spring", "microservices",
    "grpc", "rest", "graphql", "event-driven", "event sourcing", "cqrs",
    "distributed systems", "scalability", "caching", "ci/cd", "observability",
    "service mesh", "elasticsearch", "rabbitmq", "kinesis", "pulsar",
}


def extract_stack(text: str | None) -> list[str]:
    if not text:
        return []
    low = text.lower()
    hits: list[str] = []
    for kw in _STACK_KEYWORDS:
        if kw in low and kw not in hits:
            hits.append(kw)
    return hits[:25]


def backend_signal_strength(stack: Iterable[str]) -> float:
    """Fraction of strong-backend-signal keywords present in stack. 0..1."""
    s = {x.lower() for x in stack}
    hits = len(s & BACKEND_SKILL_SIGNALS)
    if hits == 0:
        return 0.0
    # 4+ strong signals = saturated
    return min(1.0, hits / 4.0)


# ---------- visa ----------

_VISA_POS = re.compile(r"\b(visa\s*sponsorship|sponsor\s+a\s+visa|h-?1b|will\s+sponsor)\b", re.I)
_VISA_NEG = re.compile(r"\b(no\s+visa\s+sponsorship|cannot\s+sponsor|not\s+sponsor|unable\s+to\s+sponsor)\b", re.I)


def infer_visa(description: str | None) -> bool | None:
    if not description:
        return None
    if _VISA_NEG.search(description):
        return False
    if _VISA_POS.search(description):
        return True
    return None


# ---------- interview style ----------

_DSA_HINTS = re.compile(r"\b(algorithm|data\s*structures|leetcode|competitive\s+programming|big-?o)\b", re.I)
_PRACTICAL_HINTS = re.compile(r"\b(take[-\s]?home|pair\s+programming|practical\s+exercise|coding\s+exercise)\b", re.I)
_SYSTEM_DESIGN_HINTS = re.compile(r"\b(system\s+design|architecture\s+(interview|round)|design\s+review)\b", re.I)


def infer_interview_style(description: str | None) -> str | None:
    if not description:
        return None
    dsa = bool(_DSA_HINTS.search(description))
    prac = bool(_PRACTICAL_HINTS.search(description))
    if dsa and prac: return "mixed"
    if dsa: return "dsa"
    if prac: return "practical"
    return None


def has_system_design_signal(description: str | None) -> bool:
    return bool(description and _SYSTEM_DESIGN_HINTS.search(description))


# ---------- text ----------

def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    try:
        return HTMLParser(html).text(separator=" ").strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\s*\([^)]*\)", " ", t)
    t = re.sub(r"\b(sr\.?|senior)\b", "senior", t)
    t = re.sub(r"\b(jr\.?|junior)\b", "junior", t)
    t = re.sub(r"\bsoftware\s+engineer\b", "software engineer", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "unknown"


def dedup_hash(company_name: str, title: str, location: str | None) -> str:
    blob = "|".join([
        slugify(company_name or ""),
        normalize_title(title or ""),
        (location or "").lower().split(",")[0].strip(),
    ])
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()
