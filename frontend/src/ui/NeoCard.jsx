import React from 'react';
import { cn } from '../utils/cn';

export function NeoCard({ children, className, hoverEffect = false, ...props }) {
    return (
        <div
            className={cn(
                "bg-surface rounded-2xl shadow-neo border border-white/5 dark:border-white/5 p-6 transition-all duration-200",
                hoverEffect && "hover:-translate-y-1 hover:shadow-lg",
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}

export function NeoSurface({ children, className, ...props }) {
    // Surface is flatter, mostly for panels inside cards or layout containers
    return (
        <div
            className={cn(
                "bg-surface rounded-xl",
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}
