"use client";
import Link from "next/link";
import type { CaseListItem } from "@/lib/types";

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  new:               { bg: "bg-blue-50",   text: "text-blue-700",    label: "New" },
  reviewing:         { bg: "bg-amber-50",  text: "text-amber-700",   label: "Reviewing" },
  approved:          { bg: "bg-emerald-50",text: "text-emerald-700", label: "Approved" },
  rejected:          { bg: "bg-slate-100", text: "text-slate-600",   label: "Rejected" },
  foia_filed:        { bg: "bg-violet-50", text: "text-violet-700",  label: "FOIA Filed" },
  records_received:  { bg: "bg-green-50",  text: "text-green-700",   label: "Records In" },
  archived:          { bg: "bg-slate-50",  text: "text-slate-500",   label: "Archived" },
};

function Stars({ score }: { score: number }) {
  return (
    <span className="inline-flex" title={`Score: ${score}/5`}>
      {[1,2,3,4,5].map(i => (
        <svg key={i} className={`w-3.5 h-3.5 ${i <= score ? "text-amber-400" : "text-slate-200"}`} fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </span>
  );
}

type Props = {
  c: CaseListItem;
  onDragStart?: (id: string) => void;
  onDragEnd?: () => void;
  isDragging?: boolean;
};

export function CaseRow({ c, onDragStart, onDragEnd, isDragging }: Props) {
  const style = STATUS_STYLES[c.status] || STATUS_STYLES.new;
  return (
    <Link
      href={`/case/${c.id}`}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", c.id);
        e.dataTransfer.effectAllowed = "move";
        onDragStart?.(c.id);
      }}
      onDragEnd={() => onDragEnd?.()}
      className={
        "relative block bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition group cursor-grab active:cursor-grabbing " +
        (isDragging ? "opacity-50 ring-2 ring-indigo-400 ring-offset-2" : "")
      }
    >
      {/* Drag handle hint — visible on hover */}
      <span className="absolute left-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-60 transition-opacity pointer-events-none">
        <svg className="w-3 h-4 text-slate-400" fill="currentColor" viewBox="0 0 20 20">
          <circle cx="6" cy="4" r="1.2" /><circle cx="10" cy="4" r="1.2" />
          <circle cx="6" cy="10" r="1.2" /><circle cx="10" cy="10" r="1.2" />
          <circle cx="6" cy="16" r="1.2" /><circle cx="10" cy="16" r="1.2" />
        </svg>
      </span>

      <div className="flex items-start justify-between gap-4 pl-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1.5">
            <Stars score={c.content_score} />
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${style.bg} ${style.text}`}>
              {style.label}
            </span>
            {c.assigned_to && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-50 text-indigo-700">
                👤 {c.assigned_to}
              </span>
            )}
          </div>
          <h3 className="font-semibold text-slate-900 group-hover:text-slate-700">
            {c.defendant_name}
            {c.defendant_age != null && (
              <span className="text-slate-500 font-normal text-sm ml-1.5">, {c.defendant_age}</span>
            )}
            {c.defendant_hometown && (
              <span className="text-slate-500 font-normal text-sm"> · {c.defendant_hometown}</span>
            )}
          </h3>
          {c.sentence_text && (
            <p className="text-sm text-slate-700 mt-1">⚖️ {c.sentence_text}</p>
          )}
          <p className="text-xs text-slate-500 mt-1.5">
            📍 {[c.county, c.state].filter(Boolean).join(", ") || c.state} · {c.sentencing_date}
          </p>
          {c.summary && (
            <p className="text-sm text-slate-600 mt-2 line-clamp-2">{c.summary}</p>
          )}
        </div>
        <svg className="w-5 h-5 text-slate-300 group-hover:text-slate-500 transition flex-shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </Link>
  );
}
