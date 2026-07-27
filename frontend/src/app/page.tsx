import React from 'react';
import CustomCursor from '@/components/CustomCursor';
import Header from '@/components/Header';
import Footer from '@/components/Footer';
import HeroSection from '@/components/HeroSection';
import ProblemSection from '@/components/ProblemSection';
import BentoGridSection from '@/components/BentoGridSection';
import EvidenceSection from '@/components/EvidenceSection';
import CTASection from '@/components/CTASection';

export default function LandingPage() {
    return (
        <div className="font-body-md text-body-md overflow-x-hidden dark text-on-background bg-background relative">
            <CustomCursor />
            <Header />
            <main className="pt-24">
                <HeroSection />
                <ProblemSection />
                <BentoGridSection />
                <EvidenceSection />
                <CTASection />
            </main>
            <Footer />
        </div>
    );
}
