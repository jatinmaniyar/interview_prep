import { useEffect, useMemo, useState } from "react";
import {
  getSDCookbook,
  listSDCompanies,
  listSDProblems,
  listSDTopics,
  type CompanyOption,
  type SDProblemSummary,
} from "../api";
import CookbookSection, {
  type SectionPayload,
} from "../components/CookbookSection";

const TYPES = [
  { id: "all", label: "All" },
  { id: "hld", label: "HLD" },
  { id: "lld", label: "LLD" },
];

const DIFFICULTIES = ["Easy", "Medium", "Hard"];

export default function SDCookbook() {
  // --- inventory state ---
  const [rows, setRows] = useState<SDProblemSummary[]>([]);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [topics, setTopics] = useState<{ topic: string; count: number }[]>([]);
  const [invLoading, setInvLoading] = useState(false);
  const [invErr, setInvErr] = useState<string | null>(null);
  const [type, setType] = useState("all");
  const [company, setCompany] = useState("");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<string[]>([]);
  const [search, setSearch] = useState("");

  // --- cookbook state ---
  const [sections, setSections] = useState<SectionPayload[]>([]);
  const [cbErr, setCbErr] = useState<string | null>(null);

  useEffect(() => {
    listSDCompanies().then(setCompanies).catch(() => setCompanies([]));
    listSDTopics().then(setTopics).catch(() => setTopics([]));
    getSDCookbook()
      .then((r) => setSections(r.sections))
      .catch((e) => setCbErr(String(e)));
  }, []);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (type !== "all") p.set("type", type);
    if (company) p.set("company", company);
    if (topic) p.set("topic", topic);
    if (search) p.set("q", search);
    difficulty.forEach((d) => p.append("difficulty", d));
    p.set("limit", "500");
    return p;
  }, [type, company, topic, difficulty, search]);

  useEffect(() => {
    setInvLoading(true);
    setInvErr(null);
    listSDProblems(params)
      .then(setRows)
      .catch((e) => setInvErr(String(e)))
      .finally(() => setInvLoading(false));
  }, [params]);

  const toggleDiff = (d: string) =>
    setDifficulty((cur) =>
      cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]
    );

  const navItems: { id: string; label: string }[] = [
    { id: "problems", label: "Problem inventory" },
    ...sections.map((s) => ({ id: s.section, label: s.title })),
  ];

  return (
    <div className="h-full flex">
      <aside className="w-60 shrink-0 border-r border-slate-800 bg-slate-950/50 overflow-y-auto">
        <div className="sticky top-0 px-4 py-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
            Cookbook
          </div>
          <nav className="flex flex-col gap-1 text-sm">
            {navItems.map((n) => (
              <a
                key={n.id}
                href={`#${n.id}`}
                className="text-slate-300 hover:text-white px-2 py-1 rounded hover:bg-slate-900"
              >
                {n.label}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {/* ---------------- Section 1: Inventory ---------------- */}
          <section id="problems" className="scroll-mt-6 pb-12 border-b border-slate-800">
            <h2 className="text-2xl font-bold text-white mb-2">
              Problem Inventory
            </h2>
            <p className="text-slate-400 mb-4 max-w-3xl leading-relaxed">
              Names + tags only — no solutions. Use this list to know <em>which</em>
              {" "}problems to study; the other sections cover <em>how</em> to approach
              them. Company tags are synthesized from public interview reports
              (TeamBlind / Glassdoor / LeetCode Discuss patterns).
            </p>

            <div className="flex flex-wrap items-end gap-4 mb-4">
              <Field label="Type">
                <div className="flex gap-2">
                  {TYPES.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setType(t.id)}
                      className={`px-3 py-1 rounded border text-sm ${
                        type === t.id
                          ? "bg-blue-600 border-blue-500"
                          : "bg-slate-900 border-slate-700"
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="Company">
                <select
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-48"
                >
                  <option value="">any</option>
                  {companies.map((c) => (
                    <option key={c.company} value={c.company}>
                      {c.company} ({c.count})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Topic">
                <select
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-48"
                >
                  <option value="">any</option>
                  {topics.map((t) => (
                    <option key={t.topic} value={t.topic}>
                      {t.topic} ({t.count})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Difficulty">
                <div className="flex gap-2">
                  {DIFFICULTIES.map((d) => (
                    <button
                      key={d}
                      onClick={() => toggleDiff(d)}
                      className={`px-2 py-1 rounded border text-sm ${
                        difficulty.includes(d)
                          ? "bg-blue-600 border-blue-500"
                          : "bg-slate-900 border-slate-700"
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="Search">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="title"
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-56"
                />
              </Field>
              <div className="text-xs text-slate-500 ml-auto">
                {invLoading ? "loading…" : `${rows.length} of 94`}
              </div>
            </div>

            {invErr && <div className="text-red-400 mb-3">{invErr}</div>}

            <table className="w-full text-sm border-collapse">
              <thead className="text-left text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2 pr-3 w-14">Type</th>
                  <th className="py-2 pr-3">Title</th>
                  <th className="py-2 pr-3 w-20">Diff</th>
                  <th className="py-2 pr-3 w-32">Topic</th>
                  <th className="py-2 pr-3">Summary</th>
                  <th className="py-2 pr-3">Companies</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-slate-900">
                    <td className="py-2 pr-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs uppercase tracking-wide ${
                          r.type === "hld"
                            ? "bg-indigo-900 text-indigo-200"
                            : "bg-emerald-900 text-emerald-200"
                        }`}
                      >
                        {r.type}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-slate-100">{r.title}</td>
                    <td className={`py-2 pr-3 text-xs ${diffColor(r.difficulty)}`}>
                      {r.difficulty || "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-400">
                      {r.topic || "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-400">
                      {r.summary || "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-400">
                      {r.companies.length ? r.companies.join(", ") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!invLoading && rows.length === 0 && (
              <div className="text-slate-400 mt-3">No matches.</div>
            )}
          </section>

          {/* ---------------- Sections 2-11: Cookbook ---------------- */}
          {cbErr && (
            <div className="text-red-400 mt-6">Cookbook load failed: {cbErr}</div>
          )}
          {sections.map((s) => (
            <div key={s.section} className="mt-10">
              <CookbookSection data={s} />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-slate-400">
      {label}
      {children}
    </label>
  );
}

function diffColor(d: string | null) {
  if (d === "Easy") return "text-green-400";
  if (d === "Medium") return "text-yellow-400";
  if (d === "Hard") return "text-red-400";
  return "text-slate-500";
}
