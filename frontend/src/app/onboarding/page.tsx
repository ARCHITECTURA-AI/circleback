"use client";

import { useEffect, useState } from "react";
import {
  getConnectionStatus,
  getGoogleLoginUrl,
  getSlackLoginUrl,
  createPerson,
  getPersons,
  triggerSync,
  type ConnectedAccount,
} from "@/lib/api";
import { LoadingState } from "@/components/EmptyState";


export default function OnboardingPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [connections, setConnections] = useState<ConnectedAccount[]>([]);
  const [loading, setLoading] = useState(true);

  // Form states for Step 2
  const [displayName, setDisplayName] = useState("");
  const [emails, setEmails] = useState("");
  const [slackIds, setSlackIds] = useState("");
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await getConnectionStatus();
      setConnections(data.accounts);

      // Check if we already have a Person mapped as is_self
      const persons = await getPersons();
      const hasSelf = persons.items.some((p) => p.is_self);

      // If they have connections and hasSelf, go straight to Step 3
      const anyConnected = data.accounts.some((a) => a.connected);
      if (anyConnected && hasSelf) {
        setStep(3);
      } else if (anyConnected) {
        setStep(2);
      }
    } catch (err) {
      console.error("Failed to load onboarding status", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
    loadStatus();
  }, []);

  const handleCreateSelf = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName) return;

    try {
      setSaving(true);
      const emailList = emails
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const slackList = slackIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      await createPerson({
        display_name: displayName,
        email_addresses: emailList,
        slack_user_ids: slackList,
        is_self: true,
      });

      setStep(3);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Failed to save details: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingState message="Checking integration states..." />;
  }

  const isGmailConnected = connections.find((c) => c.provider === "google")?.connected;
  const isSlackConnected = connections.find((c) => c.provider === "slack")?.connected;

  return (
    <div className="space-y-6">
      {/* Step Indicators */}
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-4">
        {([1, 2, 3] as const).map((s) => (
          <div key={s} className="flex items-center gap-2">
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                step === s
                  ? "bg-indigo-600 text-white"
                  : step > s
                  ? "bg-emerald-500 text-white"
                  : "bg-slate-200 dark:bg-slate-800 text-slate-500"
              }`}
            >
              {s}
            </span>
            <span
              className={`text-xs font-medium ${
                step === s ? "text-slate-900 dark:text-white" : "text-slate-400"
              }`}
            >
              {s === 1 ? "Connect" : s === 2 ? "Identity" : "Ready"}
            </span>
          </div>
        ))}
      </div>

      {/* Step 1: Connect accounts */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Connect Channels</h3>
            <p className="text-sm text-slate-500">
              Select one or both channels to connect. Circle Back will scan incoming messages for commitment text.
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-800 p-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">✉️</span>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Gmail Integration</h4>
                  <p className="text-xs text-slate-400">Restricted scopes, read-only sync</p>
                </div>
              </div>
              <div>
                {isGmailConnected ? (
                  <span className="text-xs font-medium text-emerald-600">✓ Connected</span>
                ) : (
                  <a
                    href={getGoogleLoginUrl()}
                    className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                  >
                    Connect
                  </a>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-800 p-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">💬</span>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Slack Workspace</h4>
                  <p className="text-xs text-slate-400">Events API subscription</p>
                </div>
              </div>
              <div>
                {isSlackConnected ? (
                  <span className="text-xs font-medium text-emerald-600">✓ Connected</span>
                ) : (
                  <a
                    href={getSlackLoginUrl()}
                    className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                  >
                    Connect
                  </a>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button
              onClick={() => setStep(2)}
              disabled={!isGmailConnected && !isSlackConnected}
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:bg-slate-300 dark:disabled:bg-slate-800"
            >
              Continue to Step 2 →
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Owner profile setup */}
      {step === 2 && (
        <form onSubmit={handleCreateSelf} className="space-y-6">
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Verify Your Identity</h3>
            <p className="text-sm text-slate-500">
              Provide your details so the pipeline can determine the direction of commitments (i.e. Owed by You vs Owed to You).
            </p>
          </div>

          <div className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="display-name" className="text-xs font-medium text-slate-500">Your Full Name</label>
              <input
                id="display-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Richard Hendricks"
                required
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="emails" className="text-xs font-medium text-slate-500">Your Primary Emails (comma-separated)</label>
              <input
                id="emails"
                type="text"
                value={emails}
                onChange={(e) => setEmails(e.target.value)}
                placeholder="richard@hooli.com, richard@piedpiper.com"
                required
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="slack-ids" className="text-xs font-medium text-slate-500">Your Slack User IDs (comma-separated)</label>
              <input
                id="slack-ids"
                type="text"
                value={slackIds}
                onChange={(e) => setSlackIds(e.target.value)}
                placeholder="U012345678"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>
          </div>

          <div className="flex justify-between pt-4">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="inline-flex items-center justify-center rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"
            >
              ← Back
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:bg-slate-400"
            >
              {saving ? "Saving..." : "Finish Onboarding →"}
            </button>
          </div>
        </form>
      )}

      {/* Step 3: Success */}
      {step === 3 && (
        <div className="space-y-6 text-center py-6">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl font-semibold text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
            🎉
          </div>
          <div className="space-y-2">
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">You&apos;re All Set!</h3>
            <p className="text-sm text-slate-500 max-w-sm mx-auto">
              Circle Back is ready to parse your connected accounts and build your personal commitment state machine database.
            </p>
          </div>

          <div className="pt-4 space-y-4">
            <button
              onClick={async () => {
                setSyncing(true);
                try {
                  await triggerSync();
                } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
                  console.error(err);
                } finally {
                  setSyncing(false);
                  window.location.href = "/dashboard";
                }
              }}
              disabled={syncing}
              className="inline-flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:bg-indigo-400"
            >
              {syncing ? "Syncing your messages..." : "Trigger First Sync & Enter Dashboard"}
            </button>
            <p className="text-xs text-slate-400">Your first sync will take a few minutes (spec §8.2).</p>
          </div>
        </div>
      )}
    </div>
  );
}
