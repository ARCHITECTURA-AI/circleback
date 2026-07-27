"use client";
import React from 'react';
import { motion } from 'framer-motion';

export default function HeroSection() {
    return (
        <section className="relative min-h-[90vh] flex items-center overflow-hidden px-margin-mobile md:px-margin-desktop">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/10 rounded-full blur-[120px] pointer-events-none" />
            <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />
            <div className="relative z-10 max-w-[1440px] mx-auto w-full grid grid-cols-1 md:grid-cols-12 gap-xl items-center">
                <motion.div 
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="md:col-span-7"
                >
                    <div className="inline-flex items-center gap-xs px-sm py-xs bg-surface-container-high border border-outline-variant/50 rounded-full mb-md">
                        <span className="status-dot bg-primary"></span>
                        <span className="font-mono-label text-mono-label text-primary uppercase">v4.2.0 Operational</span>
                    </div>
                    <h1 className="font-headline-lg text-headline-lg md:text-5xl lg:text-7xl mb-md tracking-tight leading-tight">
                        The <span className="text-primary italic">State Machine</span><br/>for Your Commitments.
                    </h1>
                    <p className="font-body-md text-body-md text-on-surface-variant max-w-[600px] mb-lg leading-relaxed">
                        Circle Back autonomously extracts promises, deadlines, and deliverables buried in your Gmail and Slack workstreams. Transforming fragmented conversations into a deterministic, immutable ledger of verified commitments.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-md">
                        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="bg-gradient-to-r from-indigo-500 to-indigo-600 border border-indigo-400 px-xl py-md rounded font-bold shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-sm">
                            Connect Gmail & Slack
                            <span className="material-symbols-outlined">arrow_forward</span>
                        </motion.button>
                        <motion.a whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} href="https://drive.google.com/file/d/1VKWTdQelv27-rnxhvJRj2Dc9YmyTJOTY/view?usp=sharing" target="_blank" rel="noopener noreferrer" className="bg-surface-container-low border border-slate-700 px-xl py-md rounded font-bold hover:bg-surface-container-high transition-colors inline-flex items-center justify-center">
                            View Simulation
                        </motion.a>
                    </div>
                </motion.div>
                <motion.div 
                    initial={{ opacity: 0, x: 30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
                    className="md:col-span-5 hidden lg:block"
                >
                    <div className="glass-panel p-md rounded-xl border-indigo-500/20 shadow-2xl relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="flex items-center justify-between mb-sm border-b border-outline-variant/30 pb-sm relative z-10">
                            <span className="font-mono-label text-mono-label text-on-surface-variant">RECENT_ACTIVITY</span>
                            <span className="material-symbols-outlined text-sm text-on-surface-variant">sync</span>
                        </div>
                        <div className="space-y-sm relative z-10">
                            <div className="p-sm bg-surface-container-lowest/50 rounded-lg border border-outline-variant/20 hover:border-primary/50 transition-colors">
                                <div className="flex justify-between items-start mb-xs">
                                    <span className="font-mono-code text-mono-code text-primary text-xs">@user_slack_id: "I'll have that report by EOD Friday."</span>
                                </div>
                                <div className="font-mono-code text-mono-code text-[11px] text-on-surface-variant bg-background p-xs rounded">
                                    {'{ "type": "COMMITMENT", "state": "OPEN", "confidence": 0.98, "deadline": "2024-10-25T17:00:00Z" }'}
                                </div>
                            </div>
                            <div className="p-sm bg-surface-container-lowest/50 rounded-lg border border-outline-variant/20 opacity-60 hover:opacity-100 hover:border-tertiary/50 transition-all">
                                <div className="flex justify-between items-start mb-xs">
                                    <span className="font-mono-code text-mono-code text-tertiary text-xs">Gmail: "Attached is the contract you requested."</span>
                                </div>
                                <div className="font-mono-code text-mono-code text-[11px] text-on-surface-variant bg-background p-xs rounded">
                                    {'{ "type": "FULFILLMENT", "state": "VERIFYING", "match_id": "CB-842" }'}
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
