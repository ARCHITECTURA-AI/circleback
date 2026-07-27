import React from 'react';

export default function Header() {
    return (
        <header className="fixed top-0 w-full z-50 bg-surface/80 dark:bg-surface-dim/80 backdrop-blur-md border-b border-outline-variant/30">
            <div className="flex justify-between items-center px-margin-desktop py-sm max-w-[1440px] mx-auto">
                <div className="flex items-center gap-sm cursor-pointer active:scale-95 transition-transform">
                    <img alt="Circle Back Logo" className="w-8 h-8 object-contain" src="https://lh3.googleusercontent.com/aida/AP1WRLsvXL0GTm0i5Bfly52RMPxR2PtnfxPRFzvmfyfmtu29DyooxZH68PclEYdzNcwlDY4d89Nwqom1F0kvWC_bw-EBPne5-nfe1vw7OoYK9R2YPFMtGFMv-4C4v7FUhZQjQ9Oof1zg73UjyEQy3d0yp0E2snz_PJwGZvjutyH8jaiWk2KpcPkSBBZ8cUT766E5V7hqZK_sxlgC1fy-8gGNDl8pZTvNkZsYAeBmUTQSO1QJhGd3kS2OP2j68Pyt" />
                    <span className="font-headline-md text-headline-md font-bold text-on-surface dark:text-on-surface">Circle Back</span>
                </div>
                <div className="hidden md:flex items-center gap-lg">
                    <nav className="flex gap-md">
                        <a className="font-body-sm text-body-sm text-primary font-bold hover:opacity-80 transition-opacity duration-200" href="#">System</a>
                        <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface hover:opacity-80 transition-opacity duration-200" href="#">Protocol</a>
                        <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface hover:opacity-80 transition-opacity duration-200" href="#">Docs</a>
                    </nav>
                    <button className="bg-primary-container text-on-primary-container px-md py-xs rounded-lg font-bold hover:opacity-80 transition-opacity duration-200 active:scale-95 transition-transform">
                        Connect
                    </button>
                </div>
                <div className="md:hidden">
                    <span className="material-symbols-outlined text-primary">menu</span>
                </div>
            </div>
        </header>
    );
}
