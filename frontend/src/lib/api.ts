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
};
