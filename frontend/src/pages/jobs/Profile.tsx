import { useEffect, useState } from "react";
import { JobsAPI, type Profile } from "../../jobs/api";

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    JobsAPI.profile().then(setP).catch((e) => setErr(String(e)));
  }, []);

  const save = async () => {
    if (!p) return;
    setBusy(true); setMsg(null);
    try {
      const r = await JobsAPI.saveProfile(p);
      setP(r);
      setMsg(`Saved. Rescored ${r.rescored} jobs.`);
    } catch (e) {
      setErr(String(e));
    } finally { setBusy(false); }
  };

  if (err) return <div className="p-6 text-red-400">{err}</div>;
  if (!p) return <div className="p-6 text-slate-400">Loading…</div>;

  const csv = (a: string[]) => a.join(", ");
  const fromCsv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  return (
    <div className="h-full overflow-auto p-6 max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Job profile</h1>
        <button onClick={save} disabled={busy}
          className="px-3 py-1 rounded border border-slate-700 hover:bg-slate-800 text-sm">
          {busy ? "Saving…" : "Save & rescore"}
        </button>
      </div>
      {msg && <div className="text-green-400 text-sm">{msg}</div>}

      <Field label="Target titles (comma separated)">
        <input value={csv(p.target_titles)}
          onChange={(e) => setP({ ...p, target_titles: fromCsv(e.target.value) })}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </Field>
      <Field label="Target companies (comma separated, exact company names)">
        <input value={csv(p.target_companies)}
          onChange={(e) => setP({ ...p, target_companies: fromCsv(e.target.value) })}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Target min comp">
          <input type="number" value={p.target_min_comp ?? ""}
            onChange={(e) => setP({ ...p, target_min_comp: e.target.value ? Number(e.target.value) : null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Field>
        <Field label="Currency">
          <select value={p.target_currency}
            onChange={(e) => setP({ ...p, target_currency: e.target.value })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1">
            {["USD", "EUR", "GBP", "INR"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Preferred remote">
          <select value={p.preferred_remote || ""}
            onChange={(e) => setP({ ...p, preferred_remote: e.target.value || null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="">any</option>
            <option value="remote">remote</option>
            <option value="hybrid">hybrid</option>
            <option value="onsite">onsite</option>
          </select>
        </Field>
        <Field label="Seniority">
          <select value={p.seniority || ""}
            onChange={(e) => setP({ ...p, seniority: e.target.value || null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="">any</option>
            {["junior", "mid", "senior", "staff", "principal", "manager"].map((s) =>
              <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Preferred countries (comma separated, ISO codes e.g. US,UK,DE)">
        <input value={csv(p.preferred_countries)}
          onChange={(e) => setP({ ...p, preferred_countries: fromCsv(e.target.value) })}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </Field>
      <Field label="Needs visa sponsorship">
        <input type="checkbox" checked={p.needs_visa}
          onChange={(e) => setP({ ...p, needs_visa: e.target.checked })} />
      </Field>
      <Field label="Stack (comma separated keywords matched against job description)">
        <input value={csv(p.stack)}
          onChange={(e) => setP({ ...p, stack: fromCsv(e.target.value) })}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </Field>
      <Field label="Domains (e.g. fintech, ml, infra)">
        <input value={csv(p.domains)}
          onChange={(e) => setP({ ...p, domains: fromCsv(e.target.value) })}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="GitHub username">
          <input value={p.github_username || ""}
            onChange={(e) => setP({ ...p, github_username: e.target.value || null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Field>
        <Field label="LeetCode">
          <input value={p.leetcode_username || ""}
            onChange={(e) => setP({ ...p, leetcode_username: e.target.value || null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Field>
        <Field label="Codeforces">
          <input value={p.codeforces_handle || ""}
            onChange={(e) => setP({ ...p, codeforces_handle: e.target.value || null })}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Field>
      </div>
      <Field label="Weaknesses / skill gaps (markdown)">
        <textarea value={p.weaknesses_md || ""}
          onChange={(e) => setP({ ...p, weaknesses_md: e.target.value || null })}
          className="w-full bg-slate-900 border border-slate-700 rounded p-2 font-mono text-sm" rows={4} />
      </Field>
      <Field label="Resume (markdown — used by /draft-outreach)">
        <textarea value={p.resume_md || ""}
          onChange={(e) => setP({ ...p, resume_md: e.target.value || null })}
          className="w-full bg-slate-900 border border-slate-700 rounded p-2 font-mono text-sm" rows={12} />
      </Field>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{label}</div>
      {children}
    </label>
  );
}
