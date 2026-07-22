"use client";

import { useEffect, useState } from "react";
import { getMetrics, type EvalMetrics } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/EmptyState";

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMetrics();
      setMetrics(data);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.message || "Failed to load metrics data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, []);

  if (loading) {
    return <LoadingState message="Running evaluation suite against labeled fixtures..." />;
  }

  if (error || !metrics) {
    return <ErrorState message={error || "Failed to run harness"} onRetry={loadData} />;
  }

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Precision & Recall Dashboard</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Evaluated against {metrics.total_tested} hand-labeled email and Slack fixtures. Updated on prompt/code updates.
        </p>
      </div>

      {/* Main Stats Row */}
      <div className="grid gap-6 sm:grid-cols-3">
        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Precision</span>
          <p className="mt-2 text-4xl font-bold text-slate-900 dark:text-white">
            {(metrics.precision * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Out of all commitments flagged, how many were correct. Bias is for high precision.
          </p>
        </div>

        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recall</span>
          <p className="mt-2 text-4xl font-bold text-slate-900 dark:text-white">
            {(metrics.recall * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Out of all actual commitments, how many did the system identify.
          </p>
        </div>

        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">F1 Score</span>
          <p className="mt-2 text-4xl font-bold text-slate-900 dark:text-white">
            {(metrics.f1 * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Harmonic mean of precision and recall. Combines performance indicators.
          </p>
        </div>
      </div>

      {/* Detail breakdowns */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Confusion matrix */}
        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Confusion Matrix</h2>
          <div className="grid grid-cols-2 gap-4 text-center">
            <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-4">
              <span className="text-xs text-slate-400 block mb-1">True Positives</span>
              <span className="text-xl font-semibold text-slate-900 dark:text-white">{metrics.tp}</span>
            </div>
            <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-4">
              <span className="text-xs text-slate-400 block mb-1">False Positives</span>
              <span className="text-xl font-semibold text-slate-900 dark:text-white">{metrics.fp}</span>
            </div>
            <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-4">
              <span className="text-xs text-slate-400 block mb-1">False Negatives</span>
              <span className="text-xl font-semibold text-slate-900 dark:text-white">{metrics.fn}</span>
            </div>
            <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-4">
              <span className="text-xs text-slate-400 block mb-1">True Negatives</span>
              <span className="text-xl font-semibold text-slate-900 dark:text-white">{metrics.tn}</span>
            </div>
          </div>
          <div className="pt-2 text-xs text-slate-500 space-y-1">
            <p><strong>Commitment Type Classification Accuracy:</strong> {metrics.type_accuracy !== null ? `${(metrics.type_accuracy * 100).toFixed(1)}%` : "N/A"}</p>
            <p><strong>Prefilter False Negatives:</strong> {metrics.prefilter_false_negatives} messages</p>
          </div>
        </div>

        {/* Evaluation Context Card */}
        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Harness Context</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            The evaluation harness runs the same LangGraph pipeline used in production but inserts controlled labeled messages. The objective is to verify prompt quality, confidence calibrations, and regex prefiltering.
          </p>
          <div className="rounded-lg bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 p-4 text-xs text-indigo-800 dark:text-indigo-300 leading-relaxed">
            📢 <strong>Precision vs Recall Bias:</strong> The spec requests prioritizing precision. A false positive triggers redundant work or false alert loops, whereas a false negative remains in the message stream for user manual verification.
          </div>
        </div>
      </div>

      {/* Examples for honest reporting (spec §12) */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Successes */}
        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-4">
          <h3 className="text-base font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            Extraction Success Examples
          </h3>
          <div className="space-y-3">
            {metrics.example_successes.map((s, idx) => (
              <div key={idx} className="text-xs p-3 rounded-lg bg-slate-50 dark:bg-slate-900/30 border border-slate-100 dark:border-slate-800 space-y-1">
                <p className="italic text-slate-700 dark:text-slate-300">&ldquo;{s.text}&rdquo;</p>
                <p className="text-slate-400">Confidence: {(s.confidence * 100).toFixed(0)}%</p>
              </div>
            ))}
          </div>
        </div>

        {/* Failures */}
        <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-4">
          <h3 className="text-base font-semibold text-red-700 dark:text-red-400 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            Extraction Failure Examples
          </h3>
          <div className="space-y-3">
            {metrics.example_failures.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No failures recorded in sample set.</p>
            ) : (
              metrics.example_failures.map((f, idx) => (
                <div key={idx} className="text-xs p-3 rounded-lg bg-slate-50 dark:bg-slate-900/30 border border-slate-100 dark:border-slate-800 space-y-1">
                  <p className="italic text-slate-700 dark:text-slate-300">&ldquo;{f.text}&rdquo;</p>
                  <p className="text-red-600 dark:text-red-400 font-semibold capitalize">Issue: {f.issue.replace("_", " ")}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
