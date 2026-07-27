"use client";
import React from 'react';
import { motion } from 'framer-motion';

export default function ProblemSection() {
    return (
        <section className="py-xl bg-surface-container-lowest relative overflow-hidden">
            <div className="max-w-[1440px] mx-auto px-margin-desktop relative z-10">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-xl items-center">
                    <motion.div 
                        initial={{ opacity: 0, y: 30 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                    >
                        <h2 className="font-headline-lg text-headline-lg mb-md">Entropy is the Enemy.</h2>
                        <p className="font-body-md text-body-md text-on-surface-variant mb-lg leading-relaxed">
                            Productivity tools fail because they rely on manual entry. If it isn&apos;t in the system, it doesn&apos;t exist. But in high-stakes environments, commitments happen in the flow of conversation, then vanish into the scroll.
                        </p>
                        <div className="space-y-md">
                            <motion.div whileHover={{ scale: 1.02 }} className="flex gap-md items-start p-sm -ml-sm rounded-lg hover:bg-surface-container-high transition-colors">
                                <div className="bg-surface-container-high p-sm rounded border border-outline-variant/30">
                                    <span className="material-symbols-outlined text-primary">priority_high</span>
                                </div>
                                <div>
                                    <h4 className="font-headline-md text-headline-md mb-xs">Context Collapse</h4>
                                    <p className="text-on-surface-variant text-body-sm">Threads grow too long. Important promises are buried under &quot;Thanks!&quot; and &quot;Received.&quot;</p>
                                </div>
                            </motion.div>
                            <motion.div whileHover={{ scale: 1.02 }} className="flex gap-md items-start p-sm -ml-sm rounded-lg hover:bg-surface-container-high transition-colors">
                                <div className="bg-surface-container-high p-sm rounded border border-outline-variant/30">
                                    <span className="material-symbols-outlined text-primary">analytics</span>
                                </div>
                                <div>
                                    <h4 className="font-headline-md text-headline-md mb-xs">Precision Over Recall</h4>
                                    <p className="text-on-surface-variant text-body-sm">We don&apos;t summarize everything. We only isolate the commitments that matter, with 99.9% accuracy.</p>
                                </div>
                            </motion.div>
                        </div>
                    </motion.div>
                    <motion.div 
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                        className="relative"
                    >
                        <div className="aspect-square glass-panel rounded-full relative flex items-center justify-center p-xl group overflow-hidden border-outline-variant/30 hover:border-primary/50 transition-colors duration-500">
                            <div className="absolute inset-0 bg-gradient-to-tr from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                            <div className="absolute inset-0 opacity-10 flex items-center justify-center rotate-45 group-hover:rotate-90 transition-transform duration-1000">
                                <span className="material-symbols-outlined text-[300px]">filter_alt</span>
                            </div>
                            <div className="text-center relative z-20">
                                <div className="text-5xl font-mono-label font-bold text-primary mb-xs">0.1%</div>
                                <div className="font-mono-label text-mono-label uppercase tracking-widest text-on-surface-variant">Noise Margin</div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
