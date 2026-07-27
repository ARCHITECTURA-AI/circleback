"use client";
import React, { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';

export default function CustomCursor() {
    const cursorX = useMotionValue(-100);
    const cursorY = useMotionValue(-100);
    const springConfig = { damping: 25, stiffness: 300, mass: 0.5 };
    const cursorXSpring = useSpring(cursorX, springConfig);
    const cursorYSpring = useSpring(cursorY, springConfig);
    const [isHovering, setIsHovering] = useState(false);

    useEffect(() => {
        const moveCursor = (e: MouseEvent) => {
            cursorX.set(e.clientX - 10);
            cursorY.set(e.clientY - 10);
        };
        document.addEventListener('mousemove', moveCursor);
        
        const interactiveEls = document.querySelectorAll('button, a, .glass-panel');
        const handleEnter = () => setIsHovering(true);
        const handleLeave = () => setIsHovering(false);
        
        interactiveEls.forEach(el => {
            el.addEventListener('mouseenter', handleEnter);
            el.addEventListener('mouseleave', handleLeave);
        });

        return () => {
            document.removeEventListener('mousemove', moveCursor);
            interactiveEls.forEach(el => {
                el.removeEventListener('mouseenter', handleEnter);
                el.removeEventListener('mouseleave', handleLeave);
            });
        };
    }, [cursorX, cursorY]);

    return (
        <motion.div 
            className="custom-cursor hidden md:block" 
            id="cursor"
            style={{ x: cursorXSpring, y: cursorYSpring, left: 0, top: 0, transition: 'none' }}
            animate={{ scale: isHovering ? 1.5 : 1, backgroundColor: isHovering ? 'rgba(192, 193, 255, 0.1)' : 'rgba(192, 193, 255, 0)' }}
        />
    );
}
