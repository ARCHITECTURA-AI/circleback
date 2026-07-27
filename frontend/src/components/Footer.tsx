import React from 'react';

export default function Footer() {
    return (
        <footer className="w-full bg-surface-container-lowest dark:bg-surface-container-lowest border-t border-outline-variant/20">
            <div className="flex flex-col md:flex-row justify-between items-center px-margin-desktop py-lg gap-md max-w-[1440px] mx-auto">
                <div className="flex flex-col items-center md:items-start gap-xs">
                    <span className="font-mono-label text-mono-label uppercase tracking-widest text-on-surface-variant">Circle Back</span>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">© 2024 Circle Back. Built with security first.</p>
                </div>
                <div className="flex gap-lg">
                    <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors duration-200 cursor-pointer" href="#">Privacy</a>
                    <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors duration-200 cursor-pointer" href="#">Terms</a>
                    <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors duration-200 cursor-pointer" href="#">Security</a>
                    <a className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors duration-200 cursor-pointer" href="#">Changelog</a>
                </div>
            </div>
        </footer>
    );
}
