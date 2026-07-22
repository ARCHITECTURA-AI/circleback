"use client";

import { useEffect, useState } from "react";
import { getReviewQueue, correctCommitment, type Commitment } from "@/lib/api";
import CommitmentCard from "@/components/CommitmentCard";
import { LoadingState, ErrorState } from "@/components/EmptyState";

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<Commitment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getReviewQueue();
      setQueue(data.items);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.message || "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
    loadData();
  }, []);

  const handleCorrect = async (id: string, action: string, params?: Record<string, string>) => {
    try {
      await correctCommitment(id, action, params);
      await loadData();
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Action failed: ${err.message}`);
    }
  };

  if (loading) {
    return <LoadingState message="Scanning inboxes for low-confidence commitments..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadData} />;
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Review Queue</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Low-confidence commitment candidates flagged by Claude. Triage them to train the extractor.
        </p>
      </div>

      {queue.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 px-8 py-16 text-center dark:border-slate-700 dark:bg-slate-900/50">
          <span className="mb-4 text-5xl block">✨</span>
          <h3 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">
            Review Queue Clean!
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No low-confidence candidates need manual triage at this time.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 p-4 text-sm text-amber-800 dark:text-amber-300">
            💡 <strong>How this works:</strong> These items scored low extraction confidence (&lt; 50%). If you mark them as <strong>Done</strong> or set a <strong>New deadline</strong>, they are saved as positive feedback. Marking them as <strong>Not a commitment</strong> flags them as false positives, updating the eval database.
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {queue.map((c) => (
              <CommitmentCard key={c.id} commitment={c} onCorrect={handleCorrect} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
