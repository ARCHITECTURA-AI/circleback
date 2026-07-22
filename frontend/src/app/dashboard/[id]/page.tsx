"use client";

import { useEffect, useState, use, useCallback } from "react";
import { getCommitmentDetail, correctCommitment, type CommitmentDetail } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/EmptyState";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function CommitmentDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const commitmentId = resolvedParams.id;
  const [commitment, setCommitment] = useState<CommitmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getCommitmentDetail(commitmentId);
      setCommitment(data);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.message || "Failed to load commitment details");
    } finally {
      setLoading(false);
    }
  }, [commitmentId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);

  const handleCorrect = async (action: string, extraParams?: Record<string, string>) => {
    try {
      await correctCommitment(commitmentId, action, extraParams);
      await loadData();
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Action failed: ${err.message}`);
    }
  };

  if (loading) {
    return <LoadingState message="Fetching commitment audit trail..." />;
  }

  if (error || !commitment) {
    return <ErrorState message={error || "Commitment not found"} onRetry={loadData} />;
  }

  const deadline = commitment.resolved_deadline
    ? new Date(commitment.resolved_deadline).toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
      })
    : null;

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Back navigation */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
      >
        <span>←</span> Back to Digest
      </Link>

      {/* Main card */}
      <div className="glass rounded-2xl p-8 shadow-md border border-slate-200 dark:border-slate-800 space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <StatusBadge status={commitment.status} />
            <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:text-slate-300">
              {commitment.commitment_type.toUpperCase()}
            </span>
          </div>
          <div className="text-sm text-slate-400">
            🎯 Extraction Confidence: {(commitment.extraction_confidence * 100).toFixed(0)}%
          </div>
        </div>

        {/* Commitment Text */}
        <div className="space-y-2">
          <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Tracked Promise</span>
          <blockquote className="text-2xl font-semibold leading-relaxed text-slate-950 dark:text-white">
            &ldquo;{commitment.raw_text_span}&rdquo;
          </blockquote>
        </div>

        {/* Deadline Information */}
        <div className="grid gap-6 sm:grid-cols-2 pt-4 border-t border-slate-100 dark:border-slate-800">
          <div>
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Resolved Deadline</span>
            <p className="mt-1 text-base font-medium text-slate-900 dark:text-white">
              {deadline || "No deadline mentioned"}
            </p>
          </div>
          <div>
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Stated Reasoning</span>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {commitment.raw_temporal_phrase ? (
                <>
                  Resolved relative phrase <code className="rounded bg-slate-100 dark:bg-slate-800 px-1 py-0.5 font-mono text-xs">&ldquo;{commitment.raw_temporal_phrase}&rdquo;</code> against anchor message timestamp ({(commitment.deadline_confidence * 100).toFixed(0)}% confidence).
                </>
              ) : (
                "No temporal keywords or deadline phrases detected in the source message."
              )}
            </p>
          </div>
        </div>

        {/* Source context */}
        {commitment.source_message_text && (
          <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-5 space-y-2">
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase block">Source Message Context</span>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Sender: <code className="rounded bg-slate-200 dark:bg-slate-800 px-1 py-0.5">{commitment.source_message_sender}</code>
            </p>
            <p className="text-sm italic leading-relaxed text-slate-700 dark:text-slate-300 max-h-40 overflow-y-auto pr-2">
              &ldquo;{commitment.source_message_text}&rdquo;
            </p>
          </div>
        )}

        {/* Action controls (spec §8.5) */}
        {!["fulfilled", "dismissed"].includes(commitment.status) && (
          <div className="flex flex-wrap gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => handleCorrect("done")}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors"
            >
              ✓ Mark as Done
            </button>
            <button
              onClick={() => handleCorrect("dismiss")}
              className="rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 transition-colors"
            >
              ✕ Not a Commitment
            </button>
            <button
              onClick={() => {
                const newDeadline = prompt("Enter new deadline (ISO format, e.g. 2025-01-15T18:00:00Z):");
                if (newDeadline) {
                  handleCorrect("new_deadline", { new_deadline: newDeadline });
                }
              }}
              className="rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors"
            >
              📅 Postpone / New Deadline
            </button>
          </div>
        )}
      </div>

      {/* Audit / Event Trail (spec §8.4) */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">Audit & Evidence Trail</h2>
        {commitment.events.length === 0 ? (
          <p className="text-sm text-slate-500">No events recorded for this commitment yet.</p>
        ) : (
          <div className="relative border-l border-slate-200 dark:border-slate-800 ml-4 space-y-8 py-2">
            {commitment.events.map((event) => (
              <div key={event.id} className="relative pl-6">
                {/* Event bullet */}
                <span className="absolute -left-[6px] top-1.5 flex h-3 w-3 items-center justify-center rounded-full bg-indigo-500 ring-4 ring-white dark:ring-slate-950" />
                
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-xs font-semibold tracking-wider text-indigo-600 dark:text-indigo-400 uppercase">
                    {event.type.replace("_", " ")}
                  </span>
                  <span className="text-xs text-slate-400">
                    {new Date(event.timestamp).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                {event.note && (
                  <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    {event.note}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
