"use client";
import React from 'react';
import { motion } from 'framer-motion';

export default function BentoGridSection() {
    const container = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: { staggerChildren: 0.2 }
        }
    };

    const item = {
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5 } }
    };

    return (
        <section className="py-xl bg-background relative z-10">
            <div className="max-w-[1440px] mx-auto px-margin-desktop">
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    className="text-center mb-xl"
                >
                    <h2 className="font-headline-lg text-headline-lg mb-sm">Automated State Detection</h2>
                    <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl mx-auto">
                        Every commitment undergoes continuous verification against incoming communication streams.
                    </p>
                </motion.div>
                <motion.div 
                    variants={container}
                    initial="hidden"
                    whileInView="show"
                    viewport={{ once: true, margin: "-100px" }}
                    className="grid grid-cols-1 md:grid-cols-3 gap-md"
                >
                    {/* State 1 */}
                    <motion.div variants={item} className="glass-panel p-lg rounded-xl border-l-4 border-l-primary group hover:bg-surface-container-high transition-colors">
                        <div className="flex items-center justify-between mb-lg">
                            <span className="material-symbols-outlined text-primary text-4xl group-hover:scale-110 transition-transform">radio_button_checked</span>
                            <span className="bg-primary/10 text-primary px-sm py-xs rounded font-mono-label text-xs">OPEN</span>
                        </div>
                        <h3 className="font-headline-md text-headline-md mb-md">Protocol: Active</h3>
                        <p className="text-on-surface-variant mb-lg font-body-sm">Commitment identified and acknowledged. Tracking fulfillment evidence in real-time.</p>
                        <pre className="bg-surface-container-lowest p-sm rounded font-mono-code text-[11px] text-primary/70">{`const state = commitment.poll();
if (state === 'pending') {
  listen(GMAIL_STREAM, SLACK_SOCKET);
}`}</pre>
                    </motion.div>
                    
                    {/* State 2 */}
                    <motion.div variants={item} className="glass-panel p-lg rounded-xl border-l-4 border-l-tertiary-container group hover:bg-surface-container-high transition-colors">
                        <div className="flex items-center justify-between mb-lg">
                            <span className="material-symbols-outlined text-tertiary-container text-4xl group-hover:scale-110 transition-transform">warning</span>
                            <span className="bg-tertiary-container/10 text-tertiary-container px-sm py-xs rounded font-mono-label text-xs">AT RISK</span>
                        </div>
                        <h3 className="font-headline-md text-headline-md mb-md">Threshold: Violated</h3>
                        <p className="text-on-surface-variant mb-lg font-body-sm">Estimated fulfillment time exceeds remaining window. No verification payload detected.</p>
                        <pre className="bg-surface-container-lowest p-sm rounded font-mono-code text-[11px] text-tertiary-container/70">{`if (now > T_MINUS_1HR && !payload) {
  emit('RISK_ALERT', { level: 'HIGH' });
  notify(owner);
}`}</pre>
                    </motion.div>

                    {/* State 3 */}
                    <motion.div variants={item} className="glass-panel p-lg rounded-xl border-l-4 border-l-green-500 group hover:bg-surface-container-high transition-colors">
                        <div className="flex items-center justify-between mb-lg">
                            <span className="material-symbols-outlined text-green-500 text-4xl group-hover:scale-110 transition-transform">check_circle</span>
                            <span className="bg-green-500/10 text-green-500 px-sm py-xs rounded font-mono-label text-xs">FULFILLED</span>
                        </div>
                        <h3 className="font-headline-md text-headline-md mb-md">Ledger: Finalized</h3>
                        <p className="text-on-surface-variant mb-lg font-body-sm">Fulfillment evidence cross-referenced and verified. Audit trail locked for archive.</p>
                        <pre className="bg-surface-container-lowest p-sm rounded font-mono-code text-[11px] text-green-500/70">{`ledger.push(proof);
commitment.close();
console.log('Fulfillment Verified');`}</pre>
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
}
