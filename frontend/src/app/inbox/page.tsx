"use client";
import { useEffect, useState, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CaseRow } from "@/components/case-row";
import { ArticlesView } from "@/components/articles-view";
import { api } from "@/lib/api";
import { TEAM_MEMBERS } from "@/lib/types";
import type { CaseListItem, Topic, User } from "@/lib/types";

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

type RunStatus = "running" | "completed" | "failed" | "cancelling" | "cancelled";
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
  return (
    <Suspense fallback={<AppShell><div className="text-slate-500">Loading inbox…</div></AppShell>}>
      <InboxInner />
    </Suspense>
  );
}

function InboxInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<User | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const [status, setStatus] = useState(() => searchParams.get("status") || "");
  const [assignedTo, setAssignedTo] = useState(() => searchParams.get("assigned_to") || "");
  const [state, setState] = useState(() => searchParams.get("state") || "");
  const [q, setQ] = useState(() => searchParams.get("q") || "");
  const [loading, setLoading] = useState(true);
  const [run, setRun] = useState<PipelineRun>(null);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [counts, setCounts] = useState<CountsPayload>({});
  const [draggingCaseId, setDraggingCaseId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false);
  const [bulkAssigning, setBulkAssigning] = useState(false);
  const [activeTopic, setActiveTopic] = useState<Topic | null>(null);
  const [searchText, setSearchText] = useState("");
  // Top-level tab: "cases" = sentenced (current view), "articles" = raw pool.
  // Persisted in URL so the tab survives refreshes / sharing links.
  const [view, setView] = useState<"cases" | "articles">(
    () => (searchParams.get("view") === "articles" ? "articles" : "cases")
  );
  const [articlePoolSize, setArticlePoolSize] = useState<number | null>(null);
  useEffect(() => {
    api.articleStatusCounts()
      .then((c) => setArticlePoolSize(c.all))
      .catch(() => {});
  }, [run?.status]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastStatusRef = useRef<RunStatus | null>(null);
  const lastNewCasesRef = useRef<number>(0);

  const refreshActiveTopic = useCallback(() => {
    api.getActiveTopic().then((t) => setActiveTopic(t as Topic)).catch(() => {});
  }, []);

  useEffect(() => {
    api.me().then((u) => setUser(u as User)).catch(() => {});
    refreshActiveTopic();
  }, [refreshActiveTopic]);

  // Mirror current filter state into the URL so going back to /inbox
  // (from a case detail page, browser Back, or refresh) restores the same tab.
  useEffect(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (assignedTo) params.set("assigned_to", assignedTo);
    if (state) params.set("state", state);
    if (q) params.set("q", q);
    if (page > 1) params.set("page", String(page));
    const qs = params.toString();
    const next = qs ? `/inbox?${qs}` : "/inbox";
    if (typeof window !== "undefined" && window.location.pathname + window.location.search !== next) {
      router.replace(next, { scroll: false });
    }
  }, [status, assignedTo, state, q, page, router]);

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

  function primeRunningState(msg: string) {
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
    setToast({ type: "ok", msg });
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(poll, 1500);
  }

  function clearRunningState() {
    setRun(null);
    lastStatusRef.current = null;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function startSearch() {
    const text = searchText.trim();
    if (!text || isRunning) return;
    primeRunningState(`Expanding query and starting…`);
    try {
      const data = await api.runSearch(text);
      if (data.already_running) {
        setToast({ type: "ok", msg: "A pipeline run is already in progress — re-attached." });
      } else {
        const qs = data.queries || [];
        // When the LLM expanded it into >1 variant, surface the variants
        // so the researcher sees what's actually being searched.
        const wasExpanded = data.expanded_by && data.expanded_by !== "fallback-split" && qs.length > 1;
        const preview = qs.slice(0, 5).join(", ") + (qs.length > 5 ? `, +${qs.length - 5} more` : "");
        setToast({
          type: "ok",
          msg: wasExpanded
            ? `✨ Expanded to ${qs.length} searches: ${preview}`
            : `✓ Running search for “${data.topic_name}”`,
        });
      }
      refreshActiveTopic();
      poll();
      setTimeout(() => setToast(null), 7000);
    } catch (e: unknown) {
      clearRunningState();
      const msg = e instanceof Error ? e.message : "unknown error";
      setToast({ type: "err", msg: `Failed to start: ${msg.slice(0, 200)}` });
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const allVisibleIds = cases.map((c) => c.id);
      const allSelected = allVisibleIds.length > 0 && allVisibleIds.every((id) => prev.has(id));
      if (allSelected) {
        const next = new Set(prev);
        for (const id of allVisibleIds) next.delete(id);
        return next;
      }
      const next = new Set(prev);
      for (const id of allVisibleIds) next.add(id);
      return next;
    });
  }

  async function bulkAssign(name: string | null) {
    if (selectedIds.size === 0) return;
    setBulkAssigning(true);
    setBulkMenuOpen(false);
    const ids = Array.from(selectedIds);
    // Optimistic UI
    setCases((cs) => cs.map((c) => (selectedIds.has(c.id) ? { ...c, assigned_to: name } : c)));
    try {
      await Promise.all(ids.map((id) => api.updateCase(id, { assigned_to: name })));
      api.caseStatusCounts().then(setCounts).catch(() => {});
      setToast({
        type: "ok",
        msg: name
          ? `✓ Assigned ${ids.length} case${ids.length === 1 ? "" : "s"} to ${name}`
          : `✓ Unassigned ${ids.length} case${ids.length === 1 ? "" : "s"}`,
      });
      setSelectedIds(new Set());
      setTimeout(() => setToast(null), 3000);
    } catch (e: unknown) {
      // On failure, reload to reconcile
      fetchCases();
      const msg = e instanceof Error ? e.message : "unknown error";
      setToast({ type: "err", msg: `Bulk assign failed: ${msg.slice(0, 200)}` });
      setTimeout(() => setToast(null), 5000);
    } finally {
      setBulkAssigning(false);
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
  const isCancelling = run?.status === "cancelling";
  const isActive = isRunning || isCancelling;

  async function handleCancel() {
    if (!isActive) return;
    try {
      await api.cancelPipeline();
      setToast({ type: "ok", msg: "Cancellation requested — pipeline will stop at the next checkpoint" });
      // Eagerly refresh run state so the banner flips to 'cancelling' fast.
      api.pipelineStatus()
        .then(r => setRun(r.run as PipelineRun))
        .catch(() => {});
      setTimeout(() => setToast(null), 4000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "cancel failed";
      setToast({ type: "err", msg: `Cancel failed: ${msg.slice(0, 200)}` });
      setTimeout(() => setToast(null), 5000);
    }
  }
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

      {isActive && (
        <div className={
          "mb-6 border rounded-xl p-4 flex items-center gap-4 " +
          (isCancelling ? "bg-amber-50 border-amber-200" : "bg-blue-50 border-blue-200")
        }>
          <svg className={"w-5 h-5 animate-spin flex-shrink-0 " + (isCancelling ? "text-amber-600" : "text-blue-600")} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <div className="flex-1 min-w-0">
            <div className={"text-sm font-medium " + (isCancelling ? "text-amber-900" : "text-blue-900")}>
              {isCancelling
                ? "Stopping pipeline — finishing current article…"
                : (
                  <>
                    Pipeline running
                    {run?.current_source && <span className="font-normal"> — currently fetching from <code className="px-1 py-0.5 rounded bg-blue-100">{run.current_source}</code></span>}
                  </>
                )}
            </div>
            <div className={"text-xs mt-0.5 " + (isCancelling ? "text-amber-700" : "text-blue-700")}>
              Fetched {run?.total_fetched ?? 0} articles · Extracted {run?.total_extracted ?? 0} · New cases {run?.total_new_cases ?? 0}
            </div>
          </div>
          <button
            type="button"
            onClick={handleCancel}
            disabled={isCancelling}
            className={
              "inline-flex items-center gap-1.5 text-sm font-semibold rounded-lg px-3.5 py-2 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 " +
              (isCancelling
                ? "bg-amber-100 text-amber-700 cursor-not-allowed"
                : "bg-white text-rose-700 border border-rose-200 hover:bg-rose-50 hover:border-rose-300 active:scale-95 focus:ring-rose-400 shadow-sm")
            }
            title={isCancelling ? "Cancellation already requested" : "Stop the pipeline after the current article"}
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <rect x="5" y="5" width="10" height="10" rx="1.5" />
            </svg>
            {isCancelling ? "Stopping…" : "Stop"}
          </button>
        </div>
      )}

      {/* Page header — title left, active-search context right. The case
          count moved to the tab badge below so this row stays calm. */}
      <header className="flex items-center justify-between gap-4 mb-6">
        <h1 className="text-[26px] leading-none font-semibold tracking-tight text-slate-900">Inbox</h1>
        {activeTopic && (
          <div className="hidden sm:inline-flex items-center gap-2 text-xs">
            <span className="text-slate-400">Active search</span>
            <span className="inline-flex items-center gap-1.5 font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
              <span className={"w-1.5 h-1.5 rounded-full bg-emerald-500 " + (isRunning ? "animate-pulse" : "")} />
              {activeTopic.name}
            </span>
          </div>
        )}
      </header>

      {/* Search-and-run — single big input + Run button. No section label;
          the placeholder text and adjacent Run button make the purpose
          self-evident. */}
      {user && (
        <form
          onSubmit={(e) => { e.preventDefault(); startSearch(); }}
          className={
            "mb-7 bg-white rounded-2xl border shadow-sm hover:shadow transition-all " +
            "flex items-center gap-2 pl-5 pr-2 py-2 " +
            (isRunning ? "border-blue-200 bg-blue-50/30" : "border-slate-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100")
          }
        >
          <svg className="w-5 h-5 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 110-16 8 8 0 010 16z" />
          </svg>
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            disabled={isRunning}
            placeholder='Describe the cases you want — e.g. "body concealment murders" or "kidnap convictions in florida"'
            className="flex-1 bg-transparent text-[15px] placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
          />
          <span className="hidden md:inline-flex items-center gap-1 text-[11px] text-slate-400 mr-1">
            <svg className="w-3 h-3 text-violet-500" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.937 15.5A2 2 0 008.5 14.063l-6.135-1.582a.5.5 0 010-.962L8.5 9.936A2 2 0 009.937 8.5l1.582-6.135a.5.5 0 01.962 0L14.063 8.5A2 2 0 0015.5 9.937l6.135 1.582a.5.5 0 010 .962L15.5 14.063a2 2 0 00-1.437 1.437l-1.582 6.135a.5.5 0 01-.962 0z" />
            </svg>
            Smart-expanded by Gemini
          </span>
          <button
            type="submit"
            disabled={isRunning || !searchText.trim()}
            className={
              "inline-flex items-center gap-2 text-white text-sm font-semibold rounded-xl px-5 py-2.5 " +
              "transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 " +
              (isRunning || !searchText.trim()
                ? "bg-slate-300 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 active:scale-95 focus:ring-blue-500 shadow-sm hover:shadow")
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
                Run
              </>
            )}
          </button>
        </form>
      )}

      {/* Top-level tabs: Filtered Cases vs. Raw Articles. */}
      <div className="flex items-center gap-1 mb-6 border-b border-slate-200">
        {([
          { key: "cases",    label: "Filtered Cases", count: total },
          { key: "articles", label: "Raw Articles",   count: articlePoolSize ?? 0 },
        ] as const).map(tab => {
          const active = view === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => {
                setView(tab.key);
                const next = new URLSearchParams(searchParams.toString());
                if (tab.key === "articles") next.set("view", "articles"); else next.delete("view");
                const qs = next.toString();
                router.replace(qs ? `/inbox?${qs}` : "/inbox");
              }}
              className={
                "relative inline-flex items-center gap-2 px-4 py-3 text-sm transition -mb-px " +
                (active
                  ? "text-slate-900 font-semibold border-b-2 border-slate-900"
                  : "text-slate-500 font-medium hover:text-slate-800 border-b-2 border-transparent")
              }
            >
              {tab.label}
              <span className={
                "inline-flex items-center justify-center min-w-[1.4rem] px-1.5 py-0.5 rounded-md text-[10px] font-semibold tabular-nums transition " +
                (active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500")
              }>
                {tab.count.toLocaleString()}
              </span>
            </button>
          );
        })}
      </div>

      {view === "articles" ? (
        <ArticlesView />
      ) : (
      <>
      {/* Filter card — narrow what's already in the inbox. Header is a
          single quiet row with a clear-all action when any filter is set. */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm mb-5 overflow-hidden">
        {(q || state || status || assignedTo) && (
          <div className="flex items-center justify-between px-5 pt-3 pb-0">
            <span className="text-xs text-slate-500">
              Filters active
            </span>
            <button
              type="button"
              onClick={() => { setPage(1); setQ(""); setState(""); setStatus(""); setAssignedTo(""); }}
              className="text-xs font-medium text-slate-500 hover:text-slate-900 transition inline-flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Clear all
            </button>
          </div>
        )}

        {/* Filter row — name search + state, each as its own pill so it's
            obvious they're separate inputs. */}
        <div className="flex items-center gap-3 px-5 py-3">
          {/* Name / summary search pill */}
          <label className="flex-1 flex items-center gap-2.5 bg-white rounded-lg border border-slate-200 px-3.5 py-2 hover:border-slate-300 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200 transition-all cursor-text">
            <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 110-16 8 8 0 010 16z" />
            </svg>
            <input
              value={q}
              onChange={(e) => { setPage(1); setQ(e.target.value); }}
              placeholder="Filter cases by defendant or summary…"
              className="flex-1 bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none min-w-0"
            />
            {q && (
              <button
                type="button"
                onClick={() => { setPage(1); setQ(""); }}
                aria-label="Clear search"
                className="text-slate-300 hover:text-slate-600 active:scale-90 transition flex-shrink-0"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </label>

          {/* State filter pill */}
          <label className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200 transition-all cursor-text">
            <svg className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a2 2 0 01-2.828 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <input
              value={state}
              onChange={(e) => { setPage(1); setState(e.target.value.toUpperCase()); }}
              placeholder="State"
              maxLength={2}
              className="w-14 bg-transparent text-sm uppercase tracking-wider font-semibold text-slate-800 placeholder:text-slate-400 placeholder:font-normal placeholder:tracking-normal focus:outline-none"
            />
            {state && (
              <button
                type="button"
                onClick={() => { setPage(1); setState(""); }}
                aria-label="Clear state"
                className="text-slate-300 hover:text-slate-600 active:scale-90 transition flex-shrink-0"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </label>
        </div>

        {/* Status segmented control — sits on a tinted band so it reads as
            a grouped control, with a quiet sentence-case label above. */}
        <div className="px-5 py-3 bg-slate-50/60 border-y border-slate-100">
          <div className="text-xs text-slate-500 mb-2">Status</div>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {STATUS_TABS.map(tab => {
              const n = tab.key === "" ? (counts.all ?? 0) : (counts[tab.key] ?? 0);
              const active = status === tab.key;
              return (
                <button
                  key={tab.key || "all"}
                  onClick={() => { setPage(1); setStatus(tab.key); }}
                  className={
                    "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400 whitespace-nowrap border " +
                    (active
                      ? `${tab.activeBg} text-white border-transparent shadow-sm`
                      : `bg-white ${tab.idleText} border-slate-200 hover:border-slate-300 hover:shadow-sm`)
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
        </div>

        {/* Assignee avatar row — same chip pattern as status so the whole
            card has one consistent visual language. */}
        <div className={
          "px-5 py-3 transition-colors " +
          (isDraggingCase ? "bg-indigo-50/40" : "")
        }>
          <div className="text-xs text-slate-500 mb-2">
            {isDraggingCase ? "↓ Drop on a name to assign" : "Assignee"}
          </div>
          <div className="flex items-center gap-2 overflow-x-auto">
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
          <p className="text-sm text-slate-500 mb-2 max-w-sm mx-auto">
            {status || state || q || assignedTo
              ? "No cases match your current filters. Try clearing them."
              : "Type keywords above (e.g. “kidnapping california”) and click Run to fetch cases."}
          </p>
        </div>
      ) : (
        <>
          {/* Select-all row */}
          <div className="flex items-center justify-between mb-2 px-1">
            <label className="inline-flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
              <span
                role="checkbox"
                aria-checked={cases.length > 0 && cases.every((c) => selectedIds.has(c.id))}
                tabIndex={0}
                onClick={toggleSelectAll}
                onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggleSelectAll(); } }}
                className={
                  "w-5 h-5 rounded-md flex items-center justify-center transition-all " +
                  (cases.length > 0 && cases.every((c) => selectedIds.has(c.id))
                    ? "bg-indigo-600 border-2 border-indigo-600"
                    : "bg-white border-2 border-slate-300 hover:border-slate-400")
                }
              >
                {cases.length > 0 && cases.every((c) => selectedIds.has(c.id)) && (
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </span>
              <span>Select all on this page</span>
            </label>
            {selectedIds.size > 0 && (
              <span className="text-xs text-slate-500">{selectedIds.size} selected</span>
            )}
          </div>
          {/* Cases grouped by FETCH date (created_at), rendered IST. */}
          {(() => {
            const dayFmt = new Intl.DateTimeFormat("en-IN", {
              timeZone: "Asia/Kolkata",
              day: "2-digit",
              month: "short",
              year: "numeric",
            });
            const todayIST = dayFmt.format(new Date());
            const yesterdayIST = dayFmt.format(new Date(Date.now() - 86400000));

            const labelFor = (iso: string): string => {
              const d = dayFmt.format(new Date(iso));
              if (d === todayIST) return `Today  ·  ${d}`;
              if (d === yesterdayIST) return `Yesterday  ·  ${d}`;
              return d;
            };

            // Group cases by fetch date, then sort groups newest-first so
            // today appears at the top, then yesterday, then older days.
            // Sort key is the UTC midnight of each case's created_at day —
            // independent of how Intl formats the date string.
            const groups: { key: string; label: string; sortKey: number; items: CaseListItem[] }[] = [];
            const lookup = new Map<string, number>();
            for (const c of cases) {
              const key = dayFmt.format(new Date(c.created_at));
              let idx = lookup.get(key);
              if (idx === undefined) {
                idx = groups.length;
                lookup.set(key, idx);
                const created = new Date(c.created_at);
                groups.push({
                  key,
                  label: labelFor(c.created_at),
                  // Use the max created_at seen for this group so far —
                  // updated below as more cases land in it.
                  sortKey: created.getTime(),
                  items: [],
                });
              }
              const created = new Date(c.created_at);
              if (created.getTime() > groups[idx].sortKey) {
                groups[idx].sortKey = created.getTime();
              }
              groups[idx].items.push(c);
            }
            groups.sort((a, b) => b.sortKey - a.sortKey);

            return (
              <div className="space-y-6">
                {groups.map(group => (
                  <section key={group.key}>
                    <div className="flex items-center gap-3 mb-3 px-1">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        {group.label}
                      </h3>
                      <span className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">
                        {group.items.length}
                      </span>
                      <div className="flex-1 h-px bg-slate-200" />
                    </div>
                    <div className="space-y-3">
                      {group.items.map(c => (
                        <CaseRow
                          key={c.id}
                          c={c}
                          isDragging={draggingCaseId === c.id}
                          onDragStart={(id) => setDraggingCaseId(id)}
                          onDragEnd={() => { setDraggingCaseId(null); setDropTarget(null); }}
                          selected={selectedIds.has(c.id)}
                          onToggleSelect={toggleSelect}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            );
          })()}
        </>
      )}

      {/* Floating bulk-action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-900 text-white rounded-2xl shadow-2xl border border-slate-700 px-4 py-3 flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4">
          <span className="inline-flex items-center gap-2 text-sm font-medium pr-1">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-indigo-500/20 text-indigo-300 text-xs font-bold">
              {selectedIds.size}
            </span>
            selected
          </span>
          <div className="w-px h-6 bg-slate-700" />
          <div className="relative">
            <button
              disabled={bulkAssigning}
              onClick={() => setBulkMenuOpen((v) => !v)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-60 disabled:cursor-wait focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1 focus:ring-offset-slate-900"
            >
              {bulkAssigning ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Assigning…
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7zM18 12h4m-2-2v4" />
                  </svg>
                  Assign to…
                </>
              )}
            </button>
            {bulkMenuOpen && (
              <div className="absolute bottom-full left-0 mb-2 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 min-w-[180px] text-slate-900">
                <button
                  onClick={() => bulkAssign(null)}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center gap-2 text-slate-600"
                >
                  <span className="w-5 h-5 rounded-full bg-slate-100 flex items-center justify-center">
                    <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636" />
                    </svg>
                  </span>
                  Unassigned
                </button>
                <div className="h-px bg-slate-100 my-1" />
                {TEAM_MEMBERS.map((name) => {
                  const colors = MEMBER_COLORS[name];
                  return (
                    <button
                      key={name}
                      onClick={() => bulkAssign(name)}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center gap-2"
                    >
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${colors.chip} ${colors.text}`}>
                        {name.charAt(0)}
                      </span>
                      {name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <button
            onClick={() => { setSelectedIds(new Set()); setBulkMenuOpen(false); }}
            disabled={bulkAssigning}
            className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-1 focus:ring-offset-slate-900"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Clear
          </button>
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
      </>
      )}
    </AppShell>
  );
}
