"use client";
import React from 'react';
import { motion } from 'framer-motion';

export default function EvidenceSection() {
    return (
        <section className="py-xl bg-surface-container relative overflow-hidden">
            <div className="max-w-[1440px] mx-auto px-margin-desktop relative z-10">
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    className="text-center max-w-[768px] mx-auto mb-xl"
                >
                    <h2 className="font-headline-lg text-headline-lg mb-md">Immutable Evidence</h2>
                    <p className="font-body-md text-body-md text-on-surface-variant">
                        We don&apos;t just &quot;read&quot; your messages. We generate cryptographically verifiable proof of work and commitments to ensure absolute clarity across teams.
                    </p>
                </motion.div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-lg items-stretch">
                    <motion.div 
                        initial={{ opacity: 0, x: -30 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.5 }}
                        className="glass-panel p-lg rounded-xl flex items-center gap-lg hover:border-primary/50 transition-colors group"
                    >
                        <div className="p-md bg-primary/10 rounded-lg shrink-0 group-hover:bg-primary/20 transition-colors">
                            <span className="material-symbols-outlined text-primary text-5xl" style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
                        </div>
                        <div>
                            <h4 className="font-headline-md text-headline-md mb-xs">Audited Transactions</h4>
                            <p className="text-on-surface-variant text-body-sm">Every change in a commitment&apos;s state is logged with a timestamp and the specific conversation excerpt that triggered it.</p>
                        </div>
                    </motion.div>
                    <motion.div 
                        initial={{ opacity: 0, x: 30 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="glass-panel p-lg rounded-xl flex items-center gap-lg hover:border-primary/50 transition-colors group"
                    >
                        <div className="p-md bg-primary/10 rounded-lg shrink-0 group-hover:bg-primary/20 transition-colors">
                            <span className="material-symbols-outlined text-primary text-5xl" style={{ fontVariationSettings: "'FILL' 1" }}>security</span>
                        </div>
                        <div>
                            <h4 className="font-headline-md text-headline-md mb-xs">Immutable Record</h4>
                            <p className="text-on-surface-variant text-body-sm">Data is processed in memory and only non-PII commitment metadata is stored on our encrypted ledger.</p>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
