"use client";

import { useEffect, useState } from "react";
import { getDigest, correctCommitment, getPersons, type Commitment } from "@/lib/api";
import CommitmentCard from "@/components/CommitmentCard";
import { LoadingState, ErrorState } from "@/components/EmptyState";
import Link from "next/link";

export default function DashboardPage() {
  const [digest, setDigest] = useState<{ made_by_user: Commitment[]; owed_to_user: Commitment[] } | null>(null);
  const [hasSelf, setHasSelf] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "made_by_user" | "owed_to_user">("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const personData = await getPersons();
      const hasSelfMapped = personData.items.some((p) => p.is_self);
      setHasSelf(hasSelfMapped);

      if (hasSelfMapped) {
        const data = await getDigest();
        setDigest(data);
      }
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.message || "Failed to load commitment digest");
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
      // Reload digest to reflect changes
      await loadData();
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Action failed: ${err.message}`);
    }
  };

  if (loading) {
    return <LoadingState message="Fetching your commitment digest..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadData} />;
  }

  if (!hasSelf) {
    return (
      <div className="space-y-6 max-w-xl mx-auto text-center py-24 animate-fade-in">
        <span className="text-5xl block mb-4">👤</span>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Identity Mapping Required</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          We need to know which email addresses and Slack user IDs belong to you (Self) before we can build your commitment digest.
        </p>
        <div className="pt-4">
          <Link
            href="/onboarding"
            className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 transition-all duration-200"
          >
            Complete Onboarding Step 2
          </Link>
        </div>
      </div>
    );
  }

  const allMade = digest?.made_by_user || [];
  const allOwed = digest?.owed_to_user || [];

  const filterCommitments = (list: Commitment[]) => {
    if (statusFilter === "all") return list;
    return list.filter((c) => c.status === statusFilter);
  };

  const filteredMade = filterCommitments(allMade);
  const filteredOwed = filterCommitments(allOwed);

  const atRiskCount = [...allMade, ...allOwed].filter((c) => c.status === "at_risk").length;
  const overdueCount = [...allMade, ...allOwed].filter((c) => c.status === "overdue").length;

  return (
    <div className="space-y-8">
      {/* Header section with high-end typography */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Commitment Digest</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Real-time tracking of commitments extracted from Gmail & Slack.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/onboarding"
            className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          >
            Connect Channels
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div className="glass rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">At Risk</span>
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              ⚠️
            </span>
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{atRiskCount}</p>
          <p className="mt-1 text-xs text-slate-400">Approaching deadline with no evidence of fulfillment</p>
        </div>

        <div className="glass rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Overdue</span>
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 text-xs font-semibold text-red-800 dark:bg-red-950/50 dark:text-red-300">
              🚨
            </span>
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{overdueCount}</p>
          <p className="mt-1 text-xs text-slate-400">Absence of evidence found after deadline passed</p>
        </div>

        <div className="glass rounded-2xl p-6 shadow-sm sm:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Total Active</span>
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-800 dark:bg-blue-950/50 dark:text-blue-300">
              📋
            </span>
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">
            {filteredMade.length + filteredOwed.length}
          </p>
          <p className="mt-1 text-xs text-slate-400">Ongoing commitments in both directions</p>
        </div>
      </div>

      {/* Tabs and Filters */}
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2">
          {(["all", "made_by_user", "owed_to_user"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                activeTab === tab
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
              }`}
            >
              {tab === "all" ? "All Commitments" : tab === "made_by_user" ? "Owed by You" : "Owed to You"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="status-filter" className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Filter Status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="at_risk">At Risk</option>
            <option value="overdue">Overdue</option>
            <option value="fulfilled">Fulfilled</option>
            <option value="renegotiated">Renegotiated</option>
            <option value="needs_clarification">Needs Clarification</option>
          </select>
        </div>
      </div>

      {/* Commitments List */}
      <div className="grid gap-8">
        {(activeTab === "all" || activeTab === "made_by_user") && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <span>📤</span> Owed by You <span className="text-xs font-normal text-slate-400">({filteredMade.length})</span>
            </h2>
            {filteredMade.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500 dark:border-slate-800">
                No commitments owed by you found matching the filter.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {filteredMade.map((c) => (
                  <CommitmentCard key={c.id} commitment={c} onCorrect={handleCorrect} />
                ))}
              </div>
            )}
          </div>
        )}

        {(activeTab === "all" || activeTab === "owed_to_user") && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <span>📥</span> Owed to You <span className="text-xs font-normal text-slate-400">({filteredOwed.length})</span>
            </h2>
            {filteredOwed.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500 dark:border-slate-800">
                No commitments owed to you found matching the filter.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {filteredOwed.map((c) => (
                  <CommitmentCard key={c.id} commitment={c} onCorrect={handleCorrect} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
