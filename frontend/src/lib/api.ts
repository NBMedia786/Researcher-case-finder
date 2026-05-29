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
  // Update a source's API credential. `field` is either "api_key" or
  // "api_token" depending on the source (see source.key_field).
  // Empty value clears the override and falls back to env var.
  updateSourceConfig: (id: string, field: "api_key" | "api_token", value: string) =>
    call(`/api/sources/${id}/config`, {
      method: "PATCH",
      body: JSON.stringify({ [field]: value }),
    }),

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
  runSearch: (search_text: string, recency_days?: number, smart_expand: boolean = true) =>
    call<{
      run_id: string;
      status: string;
      already_running: boolean;
      topic_id: string;
      topic_name: string;
      queries: string[];
      expanded_by: string | null;
    }>("/api/admin/run-search", {
      method: "POST",
      body: JSON.stringify({ search_text, recency_days, smart_expand }),
    }),
  cancelPipeline: () =>
    call<{
      cancelled: boolean;
      reason?: string;
      run_id?: string;
      status?: "cancelling";
      already_requested?: boolean;
    }>("/api/admin/cancel-pipeline", { method: "POST" }),
  pipelineStatus: () => call<{
    run: null | {
      id: string;
      status: "running" | "completed" | "failed" | "cancelling" | "cancelled";
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

  // Raw articles (the full pool, including rejects) — powers the
  // "Raw Articles" tab next to the inbox.
  listArticles: (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    return call<{
      items: import("./types").ArticleListItem[];
      total: number;
      page: number;
      page_size: number;
    }>(`/api/articles?${qs.toString()}`);
  },
  articleStatusCounts: () =>
    call<{ all: number; extracted: number; no_match: number; failed: number; pending: number }>(
      "/api/articles/_status_counts"
    ),
  articleSources: () =>
    call<{ sources: { name: string; count: number }[] }>("/api/articles/_sources"),
  promoteArticle: (
    id: string,
    body: { defendant_name?: string; sentencing_date?: string; state?: string; notes?: string } = {}
  ) =>
    call<{ case_id: string; created: boolean; reused_existing: boolean }>(
      `/api/articles/${id}/promote`,
      { method: "POST", body: JSON.stringify(body) }
    ),
};
