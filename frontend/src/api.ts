export type ProblemSummary = {
  id: number;
  title: string;
  slug: string;
  difficulty: string;
  is_premium: boolean;
  status: string;
};

export type SampleTest = {
  id: number;
  input_json: string;
  expected_output_json: string;
};

export type ProblemDetailT = {
  id: number;
  title: string;
  slug: string;
  difficulty: string;
  is_premium: boolean;
  description_md: string | null;
  examples_json: string | null;
  constraints_md: string | null;
  topics_json: string | null;
  boilerplate_python: string | null;
  boilerplate_cpp: string | null;
  method_signature: string | null;
  solutions: { language: string; code: string; walkthrough_md: string | null }[];
  sample_tests: SampleTest[];
  test_count: number;
  status: string;
  notes_md: string | null;
};

export type RunResult = {
  compile_error?: string;
  results: {
    test_id: number;
    category: string;
    passed: boolean;
    input: unknown;
    expected: unknown;
    actual: unknown;
    error: string | null;
    runtime_ms: number;
  }[];
  passed: number;
  total: number;
  runtime_ms: number;
  submission_id?: number;
};

const API = "/api";

export async function listProblems(params: URLSearchParams): Promise<ProblemSummary[]> {
  const r = await fetch(`${API}/problems?${params}`);
  if (!r.ok) throw new Error(`list failed: ${r.status}`);
  return r.json();
}

export async function getProblem(id: number): Promise<ProblemDetailT> {
  const r = await fetch(`${API}/problems/${id}`);
  if (!r.ok) throw new Error(`get failed: ${r.status}`);
  return r.json();
}

export async function runCode(
  problem_id: number,
  language: string,
  code: string
): Promise<RunResult> {
  const r = await fetch(`${API}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id, language, code }),
  });
  if (!r.ok) throw new Error(`run failed: ${r.status}`);
  return r.json();
}

export async function submitCode(
  problem_id: number,
  language: string,
  code: string
): Promise<RunResult> {
  const r = await fetch(`${API}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id, language, code }),
  });
  if (!r.ok) throw new Error(`submit failed: ${r.status}`);
  return r.json();
}
