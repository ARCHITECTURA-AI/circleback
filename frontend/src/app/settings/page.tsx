"use client";

import { useEffect, useState } from "react";
import {
  getConnectionStatus,
  getGoogleLoginUrl,
  getSlackLoginUrl,
  getPersons,
  createPerson,
  deleteAllData,
  type ConnectedAccount,
  type Person,
} from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/EmptyState";

export default function SettingsPage() {
  const [connections, setConnections] = useState<ConnectedAccount[]>([]);
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form states for creating a new person mapping
  const [displayName, setDisplayName] = useState("");
  const [emails, setEmails] = useState("");
  const [slackIds, setSlackIds] = useState("");
  const [isSelf, setIsSelf] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const connData = await getConnectionStatus();
      const personData = await getPersons();
      setConnections(connData.accounts);
      setPersons(personData.items);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      setError(err.message || "Failed to load settings data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
    loadData();
  }, []);

  const handleCreatePerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName) return;

    try {
      setCreating(true);
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
        is_self: isSelf,
      });

      // Reset form
      setDisplayName("");
      setEmails("");
      setSlackIds("");
      setIsSelf(false);

      // Reload
      const personData = await getPersons();
      setPersons(personData.items);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Failed to save mapping: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteAllData = async () => {
    const confirmed = confirm(
      "⚠️ DANGER ZONE! This will permanently delete all your connected accounts, tokens, messages, commitments, and person mappings from the database. This cannot be undone. Are you absolutely sure?"
    );
    if (!confirmed) return;

    try {
      setLoading(true);
      const res = await deleteAllData();
      alert(res.message || "All data has been purged.");
      window.location.href = "/";
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      alert(`Purge failed: ${err.message}`);
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading your preferences..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadData} />;
  }

  return (
    <div className="space-y-10 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Settings</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Manage your integrations, manual cross-channel identity mapping, and account data privacy.
        </p>
      </div>

      {/* Connected Accounts Section */}
      <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Connected Channels</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Authorize Circle Back to read your messages and parse commitments.
          </p>
        </div>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {connections.map((acc) => (
            <div key={acc.provider} className="flex items-center justify-between py-4 first:pt-0 last:pb-0">
              <div className="flex items-center gap-3">
                <span className="text-2xl">
                  {acc.provider === "google" ? "✉️" : "💬"}
                </span>
                <div>
                  <h3 className="text-sm font-semibold capitalize text-slate-900 dark:text-white">
                    {acc.provider === "google" ? "Gmail" : "Slack"}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {acc.connected ? `Connected: ${acc.scope}` : "Not connected"}
                  </p>
                </div>
              </div>

              <div>
                {acc.connected ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Active
                  </span>
                ) : (
                  <a
                    href={acc.provider === "google" ? getGoogleLoginUrl() : getSlackLoginUrl()}
                    className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                  >
                    Connect
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Manual Person Mapping (spec §6.5) */}
      <div className="glass rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Identity Mapping</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Link email addresses and Slack user IDs to consolidate identity across channels.
          </p>
        </div>

        {/* Existing mappings */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Current Mappings</h3>
          {persons.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No identity mappings seeded yet.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {persons.map((p) => (
                <div key={p.id} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                      {p.display_name} {p.is_self && <span className="text-xs font-normal text-indigo-500 dark:text-indigo-400">(Self)</span>}
                    </h4>
                  </div>
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-slate-500">
                      <strong>Emails:</strong> {p.email_addresses.join(", ") || "None"}
                    </p>
                    <p className="text-xs text-slate-500">
                      <strong>Slack IDs:</strong> {p.slack_user_ids.join(", ") || "None"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Create mapping form */}
        <form onSubmit={handleCreatePerson} className="space-y-4 pt-4 border-t border-slate-100 dark:border-slate-800">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Add New Mapping</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="display-name" className="text-xs font-medium text-slate-500">Full Name</label>
              <input
                id="display-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Alice Smith"
                required
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="emails" className="text-xs font-medium text-slate-500">Email Addresses (comma-separated)</label>
              <input
                id="emails"
                type="text"
                value={emails}
                onChange={(e) => setEmails(e.target.value)}
                placeholder="alice@co.com, alice.smith@gmail.com"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="slack-ids" className="text-xs font-medium text-slate-500">Slack User IDs (comma-separated)</label>
              <input
                id="slack-ids"
                type="text"
                value={slackIds}
                onChange={(e) => setSlackIds(e.target.value)}
                placeholder="U12345678"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none dark:border-slate-800 dark:bg-slate-950"
              />
            </div>
            <div className="flex items-center pt-6">
              <input
                id="is-self"
                type="checkbox"
                checked={isSelf}
                onChange={(e) => setIsSelf(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="is-self" className="ml-2 text-sm text-slate-600 dark:text-slate-400">
                This is the Account Owner (Self)
              </label>
            </div>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-400 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors"
          >
            {creating ? "Adding..." : "Add Identity Mapping"}
          </button>
        </form>
      </div>

      {/* Danger Zone */}
      <div className="glass rounded-2xl p-6 shadow-sm border border-red-200 dark:border-red-900/50 space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-red-700 dark:text-red-400">Danger Zone</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Actions here are irreversible and delete user configuration and credentials.
          </p>
        </div>

        <div className="pt-2">
          <button
            onClick={handleDeleteAllData}
            className="rounded-lg bg-red-600 hover:bg-red-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors"
          >
            Disconnect and Delete My Data
          </button>
        </div>
      </div>
    </div>
  );
}
