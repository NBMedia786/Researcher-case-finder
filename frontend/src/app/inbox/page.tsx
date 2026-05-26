"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { AppShell } from "@/components/app-shell";
import { CaseRow } from "@/components/case-row";
import { api } from "@/lib/api";
import { TEAM_MEMBERS } from "@/lib/types";
import type { CaseListItem, User } from "@/lib/types";

const STATUS_TABS: Array<{ key: string; label: string; dot: string; activeBg: string; idleText: string }> = [
  { key: "",         label: "All",      dot: "bg-slate-400",   activeBg: "bg-slate-900",   idleText: "text-slate-700" },
  { key: "new",      label: "New",      dot: "bg-blue-500",    activeBg: "bg-blue-600",    idleText: "text-blue-700" },
  { key: "approved", label: "Approved", dot: "bg-emerald-500", activeBg: "bg-emerald-600", idleText: "text-emerald-700" },
  { key: "rejected", label: "Rejected", dot: "bg-rose-500",    activeBg: "bg-rose-600",    idleText: "text-rose-700" },
];

const MEMBER_COLORS: Record<string, { bg: string; text: string; chip: string }> = {
  Gagandeep: { bg: "bg-indigo-600",  text: "text-indigo-700",  chip: "bg-indigo-100"  },
  Rudransh:  { bg: "bg-emerald-600", text: "text-emerald-700", chip: "bg-emerald-100" },
  Piyush:    { bg: "bg-amber-600",   text: "text-amber-700",   chip: "bg-amber-100"   },
  Cyrus:     { bg: "bg-rose-600",    text: "text-rose-700",    chip: "bg-rose-100"    },
  Shivanshi: { bg: "bg-violet-600",  text: "text-violet-700",  chip: "bg-violet-100"  },
  Vandana:   { bg: "bg-teal-600",    text: "text-teal-700",    chip: "bg-teal-100"    },
};

type RunStatus = "running" | "completed" | "failed";
type PipelineRun = {
  id: string;
  status: RunStatus;
  current_source: string | null;
  total_fetched: number;
  total_extracted: number;
  total_new_cases: number;
  errors: string[];
} | null;

type CountsPayload = Record<string, number> & {
  by_assignee?: Record<string, number>;
};

export default function InboxPage() {
  const [user, setUser] = useState<User | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [run, setRun] = useState<PipelineRun>(null);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [counts, setCounts] = useState<CountsPayload>({});
  const [draggingCaseId, setDraggingCaseId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastStatusRef = useRef<RunStatus | null>(null);
  const lastNewCasesRef = useRef<number>(0);

  useEffect(() => {
    api.me().then((u) => setUser(u as User)).catch(() => {});
  }, []);

  const fetchCases = useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 25 };
    if (status) params.status = status;
    if (state) params.state = state;
    if (q) params.q = q;
    if (assignedTo) params.assigned_to = assignedTo;
    api.listCases(params)
      .then((r: unknown) => {
        const data = r as { items: CaseListItem[]; total: number };
        setCases(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
    api.caseStatusCounts().then(setCounts).catch(() => {});
  }, [page, status, state, q, assignedTo]);

  useEffect(() => { fetchCases(); }, [fetchCases]);

  const poll = useCallback(async () => {
    try {
      const data = await api.pipelineStatus();
      setRun(data.run);
      if (data.run) {
        if (data.run.total_new_cases > lastNewCasesRef.current) {
          lastNewCasesRef.current = data.run.total_new_cases;
          fetchCases();
        }
        const justFinished = lastStatusRef.current === "running" && data.run.status !== "running";
        lastStatusRef.current = data.run.status;
        if (data.run.status !== "running") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          if (justFinished) {
            if (data.run.status === "completed") {
              setToast({
                type: "ok",
                msg: `✓ Pipeline finished — ${data.run.total_new_cases} new cases (fetched ${data.run.total_fetched}, extracted ${data.run.total_extracted})`,
              });
            } else {
              setToast({
                type: "err",
                msg: `Pipeline failed: ${(data.run.errors || []).slice(0, 1).join(" | ") || "unknown error"}`,
              });
            }
            fetchCases();
            setTimeout(() => setToast(null), 12000);
          }
        }
      }
    } catch {
      /* ignore polling errors */
    }
  }, [fetchCases]);

  useEffect(() => {
    if (!user) return;
    api.pipelineStatus().then((d) => {
      setRun(d.run);
      if (d.run?.status === "running") {
        lastStatusRef.current = "running";
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(poll, 1500);
      }
    }).catch(() => {});
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [user, poll]);

  async function startPipeline() {
    lastStatusRef.current = "running";
    setRun({
      id: "pending",
      status: "running",
      current_source: null,
      total_fetched: 0,
      total_extracted: 0,
      total_new_cases: 0,
      errors: [],
    });
    setToast({ type: "ok", msg: "Pipeline starting…" });
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(poll, 1500);

    try {
      const data = await api.runPipeline();
      if (data.already_running) {
        setToast({ type: "ok", msg: "A pipeline run is already in progress — re-attached." });
      } else {
        setToast({ type: "ok", msg: "Pipeline started. Watching progress live…" });
      }
      poll();
      setTimeout(() => setToast(null), 5000);
    } catch (e: unknown) {
      setRun(null);
      lastStatusRef.current = null;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      const msg = e instanceof Error ? e.message : "unknown error";
      setToast({ type: "err", msg: `Failed to start: ${msg.slice(0, 200)}` });
    }
  }

  async function handleDropAssign(target: string, caseId: string) {
    const name = target === "__unassigned__" ? null : target;
    const prevCase = cases.find(c => c.id === caseId);
    if (!prevCase) return;
    // Optimistic UI update so the chip count + row badge change instantly
    setCases(cs => cs.map(c => c.id === caseId ? { ...c, assigned_to: name } : c));
    setToast({
      type: "ok",
      msg: name ? `✓ Assigned ${prevCase.defendant_name} to ${name}` : `✓ Unassigned ${prevCase.defendant_name}`,
    });
    try {
      await api.updateCase(caseId, { assigned_to: name });
      api.caseStatusCounts().then(setCounts).catch(() => {});
      setTimeout(() => setToast(null), 2500);
    } catch (e: unknown) {
      // Roll back on failure
      setCases(cs => cs.map(c => c.id === caseId ? { ...c, assigned_to: prevCase.assigned_to } : c));
      const msg = e instanceof Error ? e.message : "unknown error";
      setToast({ type: "err", msg: `Failed to assign: ${msg.slice(0, 200)}` });
      setTimeout(() => setToast(null), 5000);
    }
  }

  const isRunning = run?.status === "running";
  const totalPages = Math.max(1, Math.ceil(total / 25));
  const assigneeCounts = counts.by_assignee || {};
  const isDraggingCase = draggingCaseId !== null;

  return (
    <AppShell>
      {toast && (
        <div className={`fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm ${
          toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {isRunning && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-4">
          <svg className="w-5 h-5 animate-spin text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-blue-900">
              Pipeline running
              {run?.current_source && <span className="font-normal"> — currently fetching from <code className="px-1 py-0.5 rounded bg-blue-100">{run.current_source}</code></span>}
            </div>
            <div className="text-xs text-blue-700 mt-0.5">
              Fetched {run?.total_fetched ?? 0} articles · Extracted {run?.total_extracted ?? 0} · New cases {run?.total_new_cases ?? 0}
            </div>
          </div>
          <span className="text-xs text-blue-600">Auto-refresh · safe to leave this page</span>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Inbox</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {total} case{total === 1 ? "" : "s"} matching your filters
          </p>
        </div>
        {user && (
          <button
            onClick={startPipeline}
            disabled={isRunning}
            className={
              "inline-flex items-center gap-2 text-white text-sm font-semibold rounded-lg px-5 py-2.5 " +
              "transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 " +
              (isRunning
                ? "bg-slate-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 hover:shadow-lg active:scale-95 focus:ring-blue-500 cursor-pointer")
            }
          >
            {isRunning ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running…
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

      {/* Unified filter bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm mb-5 overflow-hidden">
        {/* Search row */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
          <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 110-16 8 8 0 010 16z" />
          </svg>
          <input
            value={q}
            onChange={(e) => { setPage(1); setQ(e.target.value); }}
            placeholder="Search defendant name or case summary…"
            className="flex-1 bg-transparent text-sm placeholder:text-slate-400 focus:outline-none"
          />
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a2 2 0 01-2.828 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <input
              value={state}
              onChange={(e) => { setPage(1); setState(e.target.value.toUpperCase()); }}
              placeholder="State"
              maxLength={2}
              className="w-12 bg-transparent text-sm placeholder:text-slate-400 focus:outline-none uppercase tracking-wider font-medium text-slate-700"
            />
          </div>
        </div>

        {/* Status segmented control */}
        <div className="flex items-center gap-1 px-4 py-3 border-b border-slate-100 overflow-x-auto">
          <span className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold mr-3 flex-shrink-0">Status</span>
          {STATUS_TABS.map(tab => {
            const n = tab.key === "" ? (counts.all ?? 0) : (counts[tab.key] ?? 0);
            const active = status === tab.key;
            return (
              <button
                key={tab.key || "all"}
                onClick={() => { setPage(1); setStatus(tab.key); }}
                className={
                  "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400 whitespace-nowrap " +
                  (active
                    ? `${tab.activeBg} text-white shadow-sm`
                    : `${tab.idleText} hover:bg-slate-100`)
                }
              >
                <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-white/70" : tab.dot}`} />
                {tab.label}
                <span className={
                  "inline-flex items-center justify-center min-w-[1.25rem] px-1.5 rounded-md text-[10px] font-semibold " +
                  (active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600")
                }>
                  {n}
                </span>
              </button>
            );
          })}
        </div>

        {/* Assignee avatar row */}
        <div className={
          "flex items-center gap-2 px-4 py-3 overflow-x-auto transition-colors " +
          (isDraggingCase ? "bg-indigo-50/40" : "")
        }>
          <span className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold mr-2 flex-shrink-0">
            {isDraggingCase ? "↓ Drop on a name to assign" : "Assignee"}
          </span>
          {/* Everyone */}
          {(() => {
            const active = assignedTo === "";
            const n = counts.all ?? 0;
            return (
              <button
                onClick={() => { setPage(1); setAssignedTo(""); }}
                className={
                  "inline-flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full text-xs font-medium transition-all active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400 whitespace-nowrap border " +
                  (active
                    ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:shadow-sm")
                }
              >
                <span className={
                  "w-5 h-5 rounded-full flex items-center justify-center " +
                  (active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-500")
                }>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87M9 12a4 4 0 100-8 4 4 0 000 8zm6 0a4 4 0 100-8 4 4 0 000 8z" />
                  </svg>
                </span>
                <span>Everyone</span>
                <span className={
                  "inline-flex items-center justify-center min-w-[1rem] h-4 px-1 rounded text-[10px] font-semibold ml-0.5 " +
                  (active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600")
                }>{n}</span>
              </button>
            );
          })()}

          {/* Unassigned (also drop target) */}
          {(() => {
            const active = assignedTo === "__unassigned__";
            const n = assigneeCounts["__unassigned__"] ?? 0;
            const isDropping = dropTarget === "__unassigned__";
            return (
              <button
                onClick={() => { setPage(1); setAssignedTo("__unassigned__"); }}
                onDragOver={(e) => { if (isDraggingCase) { e.preventDefault(); setDropTarget("__unassigned__"); } }}
                onDragLeave={() => setDropTarget((t) => t === "__unassigned__" ? null : t)}
                onDrop={(e) => {
                  e.preventDefault();
                  const caseId = e.dataTransfer.getData("text/plain");
                  setDropTarget(null);
                  if (caseId) handleDropAssign("__unassigned__", caseId);
                }}
                className={
                  "inline-flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full text-xs font-medium transition-all active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400 whitespace-nowrap border " +
                  (isDropping
                    ? "bg-slate-100 text-slate-900 border-slate-500 scale-110 shadow-lg ring-2 ring-slate-400"
                    : active
                      ? "bg-slate-700 text-white border-slate-700 shadow-sm"
                      : "bg-white text-slate-600 border-dashed border-slate-300 hover:border-slate-400 hover:shadow-sm")
                }
              >
                <span className={
                  "w-5 h-5 rounded-full flex items-center justify-center " +
                  (active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-400")
                }>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                </span>
                <span>Unassigned</span>
                <span className={
                  "inline-flex items-center justify-center min-w-[1rem] h-4 px-1 rounded text-[10px] font-semibold ml-0.5 " +
                  (active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600")
                }>{n}</span>
              </button>
            );
          })()}

          {/* Divider */}
          <div className="w-px h-6 bg-slate-200 mx-1 flex-shrink-0" />

          {TEAM_MEMBERS.map(name => {
            const colors = MEMBER_COLORS[name];
            const active = assignedTo === name;
            const n = assigneeCounts[name] ?? 0;
            const isDropping = dropTarget === name;
            return (
              <button
                key={name}
                onClick={() => { setPage(1); setAssignedTo(name); }}
                onDragOver={(e) => { if (isDraggingCase) { e.preventDefault(); setDropTarget(name); } }}
                onDragLeave={() => setDropTarget((t) => t === name ? null : t)}
                onDrop={(e) => {
                  e.preventDefault();
                  const caseId = e.dataTransfer.getData("text/plain");
                  setDropTarget(null);
                  if (caseId) handleDropAssign(name, caseId);
                }}
                className={
                  "inline-flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full text-xs font-medium transition-all active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400 whitespace-nowrap border " +
                  (isDropping
                    ? `${colors.bg} text-white border-transparent scale-110 shadow-lg ring-2 ring-offset-1 ring-slate-300`
                    : active
                      ? `${colors.bg} text-white border-transparent shadow-sm`
                      : `bg-white ${colors.text} border-slate-200 hover:border-slate-300 hover:shadow-sm hover:-translate-y-px ` +
                        (isDraggingCase ? "ring-1 ring-dashed ring-slate-300 animate-pulse" : ""))
                }
              >
                <span className={
                  "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold " +
                  (active || isDropping ? "bg-white/20 text-white" : `${colors.chip} ${colors.text}`)
                }>
                  {name.charAt(0)}
                </span>
                <span>{name}</span>
                <span className={
                  "inline-flex items-center justify-center min-w-[1rem] h-4 px-1 rounded text-[10px] font-semibold ml-0.5 " +
                  (active || isDropping ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600")
                }>{n}</span>
              </button>
            );
          })}
        </div>
      </div>

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
            {status || state || q || assignedTo
              ? "No cases match your current filters. Try clearing them."
              : "Run the pipeline to ingest news articles and populate the inbox."}
          </p>
          {user && !status && !state && !q && !assignedTo && !isRunning && (
            <button
              onClick={startPipeline}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition-all shadow-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Run pipeline now
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {cases.map(c => (
            <CaseRow
              key={c.id}
              c={c}
              isDragging={draggingCaseId === c.id}
              onDragStart={(id) => setDraggingCaseId(id)}
              onDragEnd={() => { setDraggingCaseId(null); setDropTarget(null); }}
            />
          ))}
        </div>
      )}

      {!loading && cases.length > 0 && (
        <div className="mt-6 flex items-center justify-between text-sm">
          <span className="text-slate-500">Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Prev
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page * 25 >= total}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
            >
              Next
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
