"use client";

import Link from "next/link";
import StatusBadge from "./StatusBadge";
import type { Commitment } from "@/lib/api";

interface CommitmentCardProps {
  commitment: Commitment;
  onCorrect?: (id: string, action: string, params?: Record<string, string>) => void;
  showActions?: boolean;
}

export default function CommitmentCard({
  commitment,
  onCorrect,
  showActions = true,
}: CommitmentCardProps) {
  const deadline = commitment.resolved_deadline
    ? new Date(commitment.resolved_deadline).toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  const typeLabels: Record<string, string> = {
    simple: "Simple",
    delegated: "Delegated",
    conditional: "Conditional",
    recurring: "Recurring",
  };

  return (
    <div className="group animate-fade-in rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:border-indigo-200 hover:shadow-md dark:border-slate-800 dark:bg-slate-950 dark:hover:border-indigo-800">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={commitment.status} />
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            {typeLabels[commitment.commitment_type] || commitment.commitment_type}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span title="Extraction confidence">
            🎯 {(commitment.extraction_confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Commitment Text */}
      <Link
        href={`/dashboard/${commitment.id}`}
        className="mb-3 block text-sm font-medium leading-relaxed text-slate-800 transition-colors hover:text-indigo-600 dark:text-slate-200 dark:hover:text-indigo-400"
      >
        &ldquo;{commitment.raw_text_span}&rdquo;
      </Link>

      {/* Deadline */}
      {(deadline || commitment.raw_temporal_phrase) && (
        <div className="mb-4 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span>📅</span>
          {deadline ? (
            <span>
              {deadline}
              {commitment.raw_temporal_phrase && (
                <span className="ml-1 text-slate-400">
                  (from &ldquo;{commitment.raw_temporal_phrase}&rdquo;)
                </span>
              )}
            </span>
          ) : (
            <span className="italic">{commitment.raw_temporal_phrase}</span>
          )}
          {commitment.deadline_confidence > 0 && (
            <span className="text-slate-400" title="Deadline confidence">
              · {(commitment.deadline_confidence * 100).toFixed(0)}% confident
            </span>
          )}
        </div>
      )}

      {/* Actions — Correction UI (spec §8.5) */}
      {showActions && onCorrect && !["fulfilled", "dismissed"].includes(commitment.status) && (
        <div className="flex gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
          <button
            onClick={() => onCorrect(commitment.id, "done")}
            className="rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-900/50"
          >
            ✓ Done
          </button>
          <button
            onClick={() => onCorrect(commitment.id, "dismiss")}
            className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            ✕ Not a commitment
          </button>
          <button
            onClick={() => {
              const newDeadline = prompt("Enter new deadline (ISO format, e.g. 2025-01-15T18:00:00Z):");
              if (newDeadline) {
                onCorrect(commitment.id, "new_deadline", { new_deadline: newDeadline });
              }
            }}
            className="rounded-lg bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-700 transition-colors hover:bg-violet-100 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:bg-violet-900/50"
          >
            📅 New deadline
          </button>
        </div>
      )}
    </div>
  );
}
