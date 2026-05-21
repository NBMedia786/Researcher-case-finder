"use client";
import { useEffect, useState, useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { CaseRow } from "@/components/case-row";
import { api } from "@/lib/api";
import type { CaseListItem, User } from "@/lib/types";

const STATUS_OPTIONS = ["new", "reviewing", "approved", "rejected",
                        "foia_filed", "records_received", "archived"];

export default function InboxPage() {
  const [user, setUser] = useState<User | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("new");
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  useEffect(() => {
    api.me().then((u) => setUser(u as User)).catch(() => {});
  }, []);

  const fetchCases = useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 25 };
    if (status) params.status = status;
    if (state) params.state = state;
    if (q) params.q = q;
    api.listCases(params)
      .then((r) => {
        const data = r as { items: CaseListItem[]; total: number };
        setCases(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [page, status, state, q]);

  useEffect(() => { fetchCases(); }, [fetchCases]);

  async function runPipeline() {
    setRunning(true);
    setToast({ type: "ok", msg: "Pipeline running… this can take 1–3 minutes." });
    try {
      const result = await api.runPipeline();
      setToast({
        type: "ok",
        msg: `✓ Ingested ${result.total_fetched} articles, created ${result.total_new_cases} new cases.`,
      });
      fetchCases();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "unknown error";
      setToast({ type: "err", msg: `Pipeline failed: ${msg.slice(0, 200)}` });
    } finally {
      setRunning(false);
      setTimeout(() => setToast(null), 8000);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 25));

  return (
    <AppShell>
      {/* Toast */}
      {toast && (
        <div className={`fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm ${
          toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Inbox</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {total} case{total === 1 ? "" : "s"} matching your filters
          </p>
        </div>
        {user?.role === "admin" && (
          <button
            onClick={runPipeline}
            disabled={running}
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg px-4 py-2 transition shadow-sm"
          >
            {running ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running pipeline…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Run pipeline now
              </>
            )}
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-2">
        <select
          value={status}
          onChange={(e) => { setPage(1); setStatus(e.target.value); }}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm bg-white"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(s => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <input
          value={state}
          onChange={(e) => { setPage(1); setState(e.target.value.toUpperCase()); }}
          placeholder="State (e.g. TX)"
          maxLength={2}
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm bg-white w-28"
        />
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder="Search defendant or summary…"
          className="border border-slate-200 rounded-md px-3 py-1.5 text-sm bg-white flex-1 min-w-48"
        />
      </div>

      {/* Body */}
      {loading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="text-slate-400 text-sm">Loading cases…</div>
        </div>
      ) : cases.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="w-16 h-16 mx-auto bg-slate-100 rounded-full flex items-center justify-center mb-4 text-3xl">
            📭
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-1">No cases yet</h3>
          <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">
            {status || state || q
              ? "No cases match your current filters. Try clearing them."
              : "Run the pipeline to ingest news articles and populate the inbox."}
          </p>
          {user?.role === "admin" && !status && !state && !q && (
            <button
              onClick={runPipeline}
              disabled={running}
              className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-60 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
            >
              {running ? "Running…" : "Run pipeline now"}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {cases.map(c => <CaseRow key={c.id} c={c} />)}
        </div>
      )}

      {/* Pagination */}
      {!loading && cases.length > 0 && (
        <div className="mt-6 flex items-center justify-between text-sm">
          <span className="text-slate-500">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-slate-200 rounded-md disabled:opacity-50 hover:bg-slate-50"
            >
              ← Prev
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page * 25 >= total}
              className="px-3 py-1.5 border border-slate-200 rounded-md disabled:opacity-50 hover:bg-slate-50"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
