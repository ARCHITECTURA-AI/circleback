"use client";
import React from 'react';
import { motion } from 'framer-motion';

export default function CTASection() {
    return (
        <section className="py-xl relative">
            <div className="absolute inset-0 bg-gradient-to-t from-primary/5 to-transparent pointer-events-none"></div>
            <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="max-w-[1440px] mx-auto px-margin-desktop text-center relative z-10"
            >
                <div className="mb-lg inline-block">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img alt="Circle Back Logo Big" className="w-16 h-16 mx-auto mb-md" src="https://lh3.googleusercontent.com/aida/AP1WRLsvXL0GTm0i5Bfly52RMPxR2PtnfxPRFzvmfyfmtu29DyooxZH68PclEYdzNcwlDY4d89Nwqom1F0kvWC_bw-EBPne5-nfe1vw7OoYK9R2YPFMtGFMv-4C4v7FUhZQjQ9Oof1zg73UjyEQy3d0yp0E2snz_PJwGZvjutyH8jaiWk2KpcPkSBBZ8cUT766E5V7hqZK_sxlgC1fy-8gGNDl8pZTvNkZsYAeBmUTQSO1QJhGd3kS2OP2j68Pyt" />
                </div>
                <h2 className="font-headline-lg text-headline-lg mb-md">Ready to Close the Loop?</h2>
                <p className="font-body-md text-body-md text-on-surface-variant max-w-[600px] mx-auto mb-lg">
                    Join 12,000+ professionals who have reclaimed 8 hours per week by offloading their commitment tracking to the state machine.
                </p>
                <div className="flex justify-center">
                    <motion.button 
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="bg-primary text-on-primary-container font-bold px-xl py-md rounded-lg shadow-xl shadow-primary/20"
                    >
                        Start Your Protocol
                    </motion.button>
                </div>
            </motion.div>
        </section>
    );
}
