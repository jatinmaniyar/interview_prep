// API client for the Job Intelligence feature. Keep types small and
// match backend/app/routers/jobs.py shapes.

export type RoleFamily =
  | "backend" | "fullstack" | "platform" | "distributed" | "infra"
  | "api" | "product_eng" | "devops" | "data_eng" | "ml" | "security"
  | "frontend" | "mobile" | "qa" | "support" | "it_admin" | "analyst"
  | "recruiter" | "low_code" | "manager" | "other";

export type Job = {
  id: string;
  source: string;
  title: string;
  title_normalized: string | null;
  company_id: number | null;
  company_name: string | null;
  seniority: string | null;
  role_family: RoleFamily | null;
  yoe_min: number | null;
  yoe_max: number | null;
  location: string | null;
  remote: "remote" | "hybrid" | "onsite" | null;
  country: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_band: "low" | "mid" | "high" | "top" | null;
  visa_sponsorship: boolean | null;
  stack: string[];
  url: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  repost_count: number;
  is_active: boolean;
  is_low_signal: boolean;
  has_system_design: boolean;
  interview_style: "dsa" | "practical" | "mixed" | null;
  hiring_urgency: number;
  competition_score: number;
  role_relevance: number;
  engineering_quality: number;
  career_leverage: number;
  job_score: number;
  duplicate_of: string | null;
  ai_summary_md: string | null;
};

export type JobDetail = Job & {
  description_md: string | null;
  score_breakdown: Record<string, number> & { weights?: Record<string, number> };
  company: {
    id: number;
    name: string;
    slug: string;
    tier: string | null;
    open_role_count: number;
    hiring_velocity_7d: number;
    hiring_velocity_30d: number;
  } | null;
  warm_contacts: WarmContact[];
  outreach_drafts: Outreach[];
};

export type Facets = {
  sources: string[];
  seniority: string[];
  role_family: string[];
  remote: string[];
  country: string[];
  tier: string[];
  band: string[];
  interview_style: string[];
};

export type CompanyRow = {
  id: number;
  slug: string;
  name: string;
  tier: string | null;
  open_role_count: number;
  hiring_velocity_7d: number;
  hiring_velocity_30d: number;
  careers_url: string | null;
  homepage_url: string | null;
};

export type CompanyDetail = CompanyRow & {
  growth_stage: string | null;
  notes_md: string | null;
  roles: Job[];
  news: { id: number; headline: string; url: string | null; kind: string | null;
          source: string | null; summary_md: string | null;
          published_at: string | null }[];
  warm_contacts: WarmContact[];
  sources: { source: string; external_org: string; enabled: boolean;
             last_status: string | null; last_run_at: string | null;
             last_count: number }[];
};

export type WarmContact = {
  id: number;
  company_id?: number;
  name: string;
  role: string | null;
  kind: string;
  github_handle: string | null;
  twitter_handle: string | null;
  website: string | null;
  public_email?: string | null;
  source_url?: string | null;
  notes_md?: string | null;
  relevance_score: number;
};

export type Outreach = {
  id: number;
  kind: string;
  subject: string | null;
  body_md: string;
  status: string;
  job_id: string | null;
  contact_id: number | null;
  company_id: number | null;
  generated_by: string;
  created_at: string;
};

export type Application = {
  id: number;
  job_id: string;
  status: string;
  applied_via: string | null;
  contact_id: number | null;
  notes_md: string | null;
  updated_at: string;
  job: {
    title: string;
    company_name: string | null;
    url: string | null;
    salary_max: number | null;
    salary_currency: string | null;
    job_score: number;
  } | null;
};

export type Profile = {
  target_titles: string[];
  target_companies: string[];
  target_min_comp: number | null;
  target_currency: string;
  preferred_remote: string | null;
  preferred_countries: string[];
  needs_visa: boolean;
  stack: string[];
  seniority: string | null;
  domains: string[];
  weaknesses_md: string | null;
  resume_md: string | null;
  github_username: string | null;
  leetcode_username: string | null;
  codeforces_handle: string | null;
  updated_at?: string;
};

export type Trends = {
  aggressive_hirers: (CompanyRow & { tier: string | null })[];
  trending_titles: { title: string; count: number }[];
  low_competition_picks: Job[];
  high_leverage_picks: Job[];
  recent_reposts: Job[];
  dream_company_openings: Job[];
};

const API = "/api";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const JobsAPI = {
  list: (params: URLSearchParams) =>
    fetch(`${API}/jobs?${params}`).then((r) => j<{ total: number; items: Job[] }>(r)),
  facets: () => fetch(`${API}/jobs/facets`).then((r) => j<Facets>(r)),
  detail: (id: string) => fetch(`${API}/jobs/${encodeURIComponent(id)}`).then((r) => j<JobDetail>(r)),
  rescore: () => fetch(`${API}/jobs/rescore`, { method: "POST" }).then((r) => j<{ rescored: number }>(r)),

  trends: () => fetch(`${API}/dashboard/trends`).then((r) => j<Trends>(r)),

  companies: (params: URLSearchParams) =>
    fetch(`${API}/co?${params}`).then((r) => j<CompanyRow[]>(r)),
  company: (slug: string) => fetch(`${API}/co/${slug}`).then((r) => j<CompanyDetail>(r)),

  sources: () => fetch(`${API}/sources`).then((r) => j<any[]>(r)),
  addSource: (body: { source: string; external_org: string; company_name?: string; enabled?: boolean }) =>
    fetch(`${API}/sources`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ ok: true }>(r)),

  profile: () => fetch(`${API}/profile`).then((r) => j<Profile>(r)),
  saveProfile: (p: Profile) =>
    fetch(`${API}/profile`, { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p) }).then((r) => j<Profile & { rescored: number }>(r)),

  warmContacts: (companyId?: number) =>
    fetch(`${API}/warm-contacts${companyId ? `?company_id=${companyId}` : ""}`)
      .then((r) => j<WarmContact[]>(r)),
  addWarm: (body: Partial<WarmContact> & { company_id: number; name: string }) =>
    fetch(`${API}/warm-contacts`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ id: number }>(r)),

  outreach: (params: URLSearchParams) =>
    fetch(`${API}/outreach?${params}`).then((r) => j<Outreach[]>(r)),
  createOutreach: (body: Partial<Outreach> & { kind: string; body_md: string }) =>
    fetch(`${API}/outreach`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ id: number }>(r)),
  patchOutreach: (id: number, body: { status?: string; body_md?: string; subject?: string }) =>
    fetch(`${API}/outreach/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ ok: true }>(r)),

  applications: () => fetch(`${API}/applications`).then((r) => j<Application[]>(r)),
  createApplication: (body: { job_id: string; status?: string; applied_via?: string;
    contact_id?: number; notes_md?: string }) =>
    fetch(`${API}/applications`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ id: number }>(r)),
  patchApplication: (id: number, body: { status?: string; notes_md?: string; applied_via?: string }) =>
    fetch(`${API}/applications/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then((r) => j<{ ok: true }>(r)),
};

export function fmtSalary(j: Pick<Job, "salary_min" | "salary_max" | "salary_currency">): string {
  if (!j.salary_max && !j.salary_min) return "—";
  const cur = j.salary_currency || "USD";
  const sym = cur === "USD" ? "$" : cur === "EUR" ? "€" : cur === "GBP" ? "£" : cur === "INR" ? "₹" : "";
  const k = (n: number) => n >= 1000 ? `${Math.round(n / 1000)}K` : `${n}`;
  if (j.salary_min && j.salary_max) return `${sym}${k(j.salary_min)}–${sym}${k(j.salary_max)}`;
  return `${sym}${k((j.salary_max || j.salary_min)!)}`;
}

export function fmtAge(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const d = Math.floor(ms / 86_400_000);
  if (d <= 0) return "today";
  if (d === 1) return "1d";
  if (d < 30) return `${d}d`;
  const m = Math.floor(d / 30);
  return `${m}mo`;
}
