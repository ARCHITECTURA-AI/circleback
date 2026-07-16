"use client";

import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen bg-slate-900 overflow-hidden text-slate-100 flex flex-col justify-between font-sans">
      {/* Background radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(99,102,241,0.15),transparent_60%)] pointer-events-none" />

      {/* Decorative top bar */}
      <header className="border-b border-slate-800/80 bg-slate-950/40 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 text-sm font-bold text-white shadow-md">
              CB
            </div>
            <span className="text-lg font-bold tracking-tight text-white">Circle Back</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
            >
              Enter Digest
            </Link>
            <Link
              href="/onboarding"
              className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-md transition-all duration-200"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex items-center justify-center py-20 px-6">
        <div className="mx-auto max-w-4xl text-center space-y-8 animate-fade-in">
          {/* Tagline */}
          <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-950/60 border border-indigo-800/50 px-3 py-1 text-xs font-semibold text-indigo-300">
            <span>💡</span> Symmetric Commitment Agent for Gmail & Slack
          </div>

          {/* Heading */}
          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-none">
            Cross-channel commitments,{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              never forgotten.
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Circle Back is a state machine that extracts commitments from your Gmail threads and Slack conversations, resolves relative deadlines, and tells you what&apos;s at risk before it becomes a broken promise.
          </p>

          {/* Call to Actions */}
          <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
            <Link
              href="/onboarding"
              className="w-full sm:w-auto rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 px-8 py-4 text-base font-bold text-white shadow-xl hover:shadow-indigo-500/20 transform hover:-translate-y-0.5 transition-all duration-200"
            >
              Connect Email & Slack
            </Link>
            <Link
              href="/dashboard"
              className="w-full sm:w-auto rounded-xl border border-slate-700 bg-slate-800/50 hover:bg-slate-800 px-8 py-4 text-base font-bold text-slate-300 hover:text-white shadow-md hover:shadow-lg transition-all duration-200"
            >
              Go to Dashboard
            </Link>
          </div>

          {/* Key showcase mockup element */}
          <div className="relative pt-12">
            <div className="absolute inset-0 bg-indigo-500/10 blur-3xl rounded-full max-w-2xl mx-auto pointer-events-none" />
            <div className="rounded-2xl bg-slate-950/80 border border-slate-800 p-6 shadow-2xl space-y-4 text-left max-w-2xl mx-auto backdrop-blur-md">
              <div className="flex items-center justify-between border-b border-slate-850 pb-3">
                <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest">Active State Monitor</span>
                <span className="inline-flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
              </div>
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-start justify-between gap-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-amber-500">at risk · owed by you</span>
                    <p className="text-sm font-medium text-slate-200 mt-0.5">&ldquo;I will send you the project roadmap by Friday EOD&rdquo;</p>
                  </div>
                  <span className="text-xs text-slate-500 bg-slate-950 px-2 py-1 rounded">24 hours left</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-start justify-between gap-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-blue-500">open · owed to you</span>
                    <p className="text-sm font-medium text-slate-200 mt-0.5">&ldquo;I&apos;ll look into the performance bug and report back tomorrow morning&rdquo;</p>
                  </div>
                  <span className="text-xs text-slate-500 bg-slate-950 px-2 py-1 rounded">Tomorrow</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/20 py-8 px-6 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} Circle Back Agent. All rights reserved.</p>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-slate-300">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-slate-300">
              Terms of Service
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
