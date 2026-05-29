"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ArticleListItem, ExtractionStatus } from "@/lib/types";

/**
 * Raw Articles tab — shows the full pool of fetched articles (matched,
 * rejected, and errored), with filters for status, source, date range,
 * and free-text. Each row carries a status badge, the search-keyword
 * (topic) chip, the LLM's rejection reason when applicable, and a
 * "Promote to case" action for false negatives.
 */

const STATUS_TABS: { key: "" | ExtractionStatus; label: string; dot: string; activeBg: string; idleText: string }[] = [
  { key: "",          label: "All",         dot: "bg-slate-400",   activeBg: "bg-slate-900",  idleText: "text-slate-700" },
  { key: "extracted", label: "Matched",     dot: "bg-emerald-500", activeBg: "bg-emerald-600",idleText: "text-emerald-700" },
  { key: "no_match",  label: "Rejected",    dot: "bg-slate-400",   activeBg: "bg-slate-700",  idleText: "text-slate-700" },
  { key: "failed",    label: "Errored",     dot: "bg-rose-500",    activeBg: "bg-rose-600",   idleText: "text-rose-700" },
];

const STATUS_BADGE: Record<ExtractionStatus, { bg: string; text: string; label: string; dot: string }> = {
  extracted: { bg: "bg-emerald-50", text: "text-emerald-700", label: "Matched",  dot: "bg-emerald-500" },
  no_match:  { bg: "bg-slate-100",  text: "text-slate-600",   label: "Rejected", dot: "bg-slate-400" },
  failed:    { bg: "bg-rose-50",    text: "text-rose-700",    label: "Errored",  dot: "bg-rose-500" },
  pending:   { bg: "bg-amber-50",   text: "text-amber-700",   label: "Pending",  dot: "bg-amber-400" },
};

function safeHref(url: string): string {
  // Article URLs come from third-party news APIs (Tavily, NewsAPI, GDELT…)
  // so defensively reject anything that isn't http(s) before rendering it
  // as a clickable href — guards against `javascript:` / `data:` injection
  // if a malicious source ever returns one.
  try {
    const u = new URL(url);
    return (u.protocol === "http:" || u.protocol === "https:") ? url : "#";
  } catch {
    return "#";
  }
}

function fmtIST(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: false,
    }).replace(",", " ·");
  } catch {
    return iso;
  }
}

type Counts = { all: number; extracted: number; no_match: number; failed: number; pending: number };

export function ArticlesView() {
  const [status, setStatus] = useState<"" | ExtractionStatus>("");
  const [source, setSource] = useState<string>("");
  const [q, setQ] = useState<string>("");
  const [since, setSince] = useState<string>("");
  const [until, setUntil] = useState<string>("");
  const [page, setPage] = useState<number>(1);

  const [items, setItems] = useState<ArticleListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [sources, setSources] = useState<{ name: string; count: number }[]>([]);
  const [counts, setCounts] = useState<Counts>({ all: 0, extracted: 0, no_match: 0, failed: 0, pending: 0 });
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [promotingId, setPromotingId] = useState<string | null>(null);
  // True while a pipeline run is fetching articles — drives the Live
  // indicator + faster polling cadence.
  const [pipelineLive, setPipelineLive] = useState<boolean>(false);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 25 };
    if (status) params.status = status;
    if (source) params.source = source;
    if (q) params.q = q;
    if (since) params.since = since;
    if (until) params.until = until;
    api.listArticles(params)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "failed to load articles";
        setToast({ type: "err", msg: msg.slice(0, 240) });
      })
      .finally(() => setLoading(false));
  }, [page, status, source, q, since, until]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.articleStatusCounts().then(setCounts).catch(() => {});
    api.articleSources().then((r) => setSources(r.sources)).catch(() => {});
  }, []);

  // Live refresh while a pipeline is running — poll pipeline-status
  // every 2.5s. When `total_fetched` ticks up, re-fetch this tab's list
  // + status counts so the researcher sees new articles arrive in real
  // time without having to refresh. When the run finishes, we do one
  // final refetch and then idle the polling.
  const lastFetchedRef = useRef<number>(-1);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      if (cancelled) return;
      try {
        const r = await api.pipelineStatus();
        const running = r.run?.status === "running";
        const totalFetched = r.run?.total_fetched ?? 0;
        setPipelineLive(running);

        // First observation: just record the baseline so we don't trigger
        // a bogus refetch on mount.
        if (lastFetchedRef.current === -1) {
          lastFetchedRef.current = totalFetched;
        } else if (totalFetched !== lastFetchedRef.current) {
          lastFetchedRef.current = totalFetched;
          load();
          api.articleStatusCounts().then(setCounts).catch(() => {});
          api.articleSources().then((r2) => setSources(r2.sources)).catch(() => {});
        }
      } catch {
        // Swallow — next tick will try again.
      }
      // Faster cadence when live, slower when idle (so we don't burn the
      // server with polls when nothing's happening).
      timer = setTimeout(tick, pipelineLive ? 2500 : 6000);
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load, pipelineLive]);

  async function promote(id: string) {
    setPromotingId(id);
    try {
      const res = await api.promoteArticle(id);
      setToast({
        type: "ok",
        msg: res.reused_existing
          ? "Merged into an existing case"
          : "Promoted — new case created",
      });
      load();
      api.articleStatusCounts().then(setCounts).catch(() => {});
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "promote failed";
      setToast({ type: "err", msg: msg.slice(0, 240) });
    } finally {
      setPromotingId(null);
      setTimeout(() => setToast(null), 4000);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 25));
  const hasFilters = !!(status || source || q || since || until);

  return (
    <>
      {toast && (
        <div className={`fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm ${
          toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Filter card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm mb-5 overflow-hidden">
        {hasFilters && (
          <div className="flex items-center justify-between px-5 pt-3 pb-0">
            <span className="text-xs text-slate-500">Filters active</span>
            <button
              type="button"
              onClick={() => { setPage(1); setStatus(""); setSource(""); setQ(""); setSince(""); setUntil(""); }}
              className="text-xs font-medium text-slate-500 hover:text-slate-900 transition inline-flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Clear all
            </button>
          </div>
        )}

        {/* Search + source + date row */}
        <div className="flex items-center gap-3 px-5 py-3 flex-wrap">
          <label className="flex-1 min-w-[200px] flex items-center gap-2.5 bg-white rounded-lg border border-slate-200 px-3.5 py-2 hover:border-slate-300 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200 transition-all cursor-text">
            <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 110-16 8 8 0 010 16z" />
            </svg>
            <input
              value={q}
              onChange={(e) => { setPage(1); setQ(e.target.value); }}
              placeholder="Search article title or text…"
              className="flex-1 bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none min-w-0"
            />
          </label>

          <select
            value={source}
            onChange={(e) => { setPage(1); setSource(e.target.value); }}
            className="bg-white rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-200 hover:border-slate-300 transition-all min-w-[160px]"
          >
            <option value="">All sources</option>
            {sources.map(s => (
              <option key={s.name} value={s.name}>{s.name} ({s.count})</option>
            ))}
          </select>

          <div className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200 transition-all">
            <span className="text-xs text-slate-400">From</span>
            <input
              type="date"
              value={since}
              onChange={(e) => { setPage(1); setSince(e.target.value); }}
              className="bg-transparent text-sm text-slate-800 focus:outline-none"
            />
            <span className="text-xs text-slate-400">To</span>
            <input
              type="date"
              value={until}
              onChange={(e) => { setPage(1); setUntil(e.target.value); }}
              className="bg-transparent text-sm text-slate-800 focus:outline-none"
            />
          </div>
        </div>

        {/* Status tabs */}
        <div className="px-5 py-3 bg-slate-50/60 border-t border-slate-100">
          <div className="text-xs text-slate-500 mb-2">Status</div>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {STATUS_TABS.map(tab => {
              const n = tab.key === "" ? counts.all : counts[tab.key];
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
      </div>

      {/* Article list */}
      {loading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="text-slate-400 text-sm">Loading articles…</div>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="w-16 h-16 mx-auto bg-slate-100 rounded-full flex items-center justify-center mb-4 text-3xl">📰</div>
          <h3 className="text-lg font-semibold text-slate-900 mb-1">No articles found</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            {hasFilters ? "Try clearing your filters." : "Run a search above to start pulling articles into the pool."}
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="text-xs text-slate-500">
              <span className="font-semibold text-slate-700">{total.toLocaleString()}</span> article{total === 1 ? "" : "s"} in your pool
              {hasFilters && " matching these filters"}
            </div>
            {pipelineLive && (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                <span className="relative flex w-1.5 h-1.5">
                  <span className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-75" />
                  <span className="relative rounded-full w-1.5 h-1.5 bg-emerald-500" />
                </span>
                Live — refreshing as the pipeline runs
              </span>
            )}
          </div>
          {(() => {
            // Group by IST fetch date so each day is its own section,
            // newest at the top — same pattern the Filtered Cases tab uses.
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
            type Group = { key: string; label: string; sortKey: number; items: ArticleListItem[] };
            const groups: Group[] = [];
            const lookup = new Map<string, number>();
            for (const a of items) {
              const key = dayFmt.format(new Date(a.created_at));
              let idx = lookup.get(key);
              if (idx === undefined) {
                idx = groups.length;
                lookup.set(key, idx);
                groups.push({
                  key,
                  label: labelFor(a.created_at),
                  sortKey: new Date(a.created_at).getTime(),
                  items: [],
                });
              }
              const t = new Date(a.created_at).getTime();
              if (t > groups[idx].sortKey) groups[idx].sortKey = t;
              groups[idx].items.push(a);
            }
            groups.sort((g1, g2) => g2.sortKey - g1.sortKey);

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
                    <div className="space-y-2.5">
                      {group.items.map(a => {
                        const badge = STATUS_BADGE[a.extraction_status];
                        const showPromote = a.extraction_status !== "extracted";
                        return (
                          <div key={a.id} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-sm hover:border-slate-300 transition">
                            <div className="flex items-start justify-between gap-4 mb-2">
                              <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                                <span className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-semibold ${badge.bg} ${badge.text}`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                                  {badge.label}
                                </span>
                                {a.topic_name && (
                                  <span
                                    className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
                                    title="Search keyword that fetched this article"
                                  >
                                    <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                                    </svg>
                                    {a.topic_name}
                                  </span>
                                )}
                                <span className="text-[11px] text-slate-500 font-medium">{a.source_name}</span>
                                <span className="text-[11px] text-slate-400">·</span>
                                <span className="text-[11px] text-slate-500">{fmtIST(a.published_at || a.created_at)} IST</span>
                              </div>
                              <a
                                href={safeHref(a.url)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[11px] text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1 flex-shrink-0"
                                title={a.url}
                              >
                                Open
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </a>
                            </div>

                            <h4 className="text-sm font-semibold text-slate-900 leading-snug mb-1.5">
                              {a.title || <span className="italic text-slate-400">(no title)</span>}
                            </h4>

                            {a.rejection_reason && (
                              <p className="text-xs text-slate-600 mb-2 leading-relaxed">
                                <span className="font-semibold text-slate-700">Why rejected: </span>
                                {a.rejection_reason}
                              </p>
                            )}

                            {(a.extracted_defendant_name || a.extracted_state || a.extracted_sentencing_date) && (
                              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500 mb-2">
                                {a.extracted_defendant_name && <span>👤 {a.extracted_defendant_name}</span>}
                                {a.extracted_state && <span>📍 {a.extracted_state}</span>}
                                {a.extracted_sentencing_date && <span>📅 {a.extracted_sentencing_date}</span>}
                              </div>
                            )}

                            <div className="flex items-center gap-2">
                              {a.extraction_status === "extracted" && a.case_id && (
                                <a
                                  href={`/case/${a.case_id}`}
                                  className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 inline-flex items-center gap-1"
                                >
                                  View case →
                                </a>
                              )}
                              {showPromote && (
                                <button
                                  type="button"
                                  onClick={() => promote(a.id)}
                                  disabled={promotingId === a.id}
                                  className={
                                    "text-[11px] font-semibold inline-flex items-center gap-1 px-2.5 py-1 rounded-md border transition " +
                                    (promotingId === a.id
                                      ? "bg-slate-50 text-slate-400 border-slate-200 cursor-wait"
                                      : "bg-white text-slate-700 border-slate-300 hover:border-slate-500 hover:text-slate-900 hover:shadow-sm")
                                  }
                                  title="Manually create a case from this article (overrides Gemini)"
                                >
                                  {promotingId === a.id ? "Promoting…" : "↑ Promote to case"}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            );
          })()}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="text-sm font-medium px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                ← Previous
              </button>
              <span className="text-xs text-slate-500">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                className="text-sm font-medium px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
