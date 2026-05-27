const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  loginWithGoogle: (idToken: string) =>
    call("/api/auth/login", { method: "POST", body: JSON.stringify({ id_token: idToken }) }),
  logout: () => call("/api/auth/logout", { method: "POST" }),
  me: () => call("/api/auth/me"),

  listCases: (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    return call(`/api/cases?${qs.toString()}`);
  },
  caseStatusCounts: () =>
    call<
      Record<string, number> & { by_assignee: Record<string, number> }
    >("/api/cases/_status_counts"),
  getCase: (id: string) => call(`/api/cases/${id}`),
  updateCase: (id: string, patch: object) =>
    call(`/api/cases/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  transitionCase: (id: string, action: string, note?: string) =>
    call(`/api/cases/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    }),

  listSources: () => call("/api/sources"),
  toggleSource: (id: string, isActive: boolean) =>
    call(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),
  runSource: (id: string) => call(`/api/sources/${id}/run`, { method: "POST" }),

  listUsers: () => call("/api/users"),
  updateUser: (id: string, patch: object) =>
    call(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  // Topics — saved search profiles that drive the pipeline.
  listTopics: () => call("/api/topics"),
  getActiveTopic: () => call("/api/topics/active"),
  createTopic: (body: { name: string; queries: string[]; extraction_criteria: string; recency_days: number }) =>
    call("/api/topics", { method: "POST", body: JSON.stringify(body) }),
  updateTopic: (id: string, patch: object) =>
    call(`/api/topics/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteTopic: (id: string) =>
    call(`/api/topics/${id}`, { method: "DELETE" }),
  activateTopic: (id: string) =>
    call(`/api/topics/${id}/activate`, { method: "POST" }),

  runPipeline: () => call<{ run_id: string; status: string; already_running: boolean }>(
    "/api/admin/run-pipeline", { method: "POST" }
  ),
  pipelineStatus: () => call<{
    run: null | {
      id: string;
      status: "running" | "completed" | "failed";
      started_at: string;
      finished_at: string | null;
      current_source: string | null;
      total_fetched: number;
      total_extracted: number;
      total_new_cases: number;
      per_source: { name: string; fetched: number; extracted: number; new_cases: number }[];
      errors: string[];
    };
  }>("/api/admin/pipeline-status"),
};
