import React, { forwardRef } from 'react';
import { cn } from '../utils/cn';

export const NeoInput = forwardRef(({ className, error, ...props }, ref) => {
    return (
        <div className="relative w-full">
            <input
                ref={ref}
                className={cn(
                    "bg-surface rounded-xl px-4 py-2.5 shadow-neo-input outline-none focus:ring-2 focus:ring-indigo-400/50 dark:focus:ring-indigo-500/50 placeholder:text-text-muted text-text-primary w-full transition-all border border-transparent dark:border-white/5",
                    error && "ring-2 ring-red-400/50 bg-red-50/10",
                    className
                )}
                {...props}
            />
            {error && <p className="mt-1 text-xs text-red-500 ml-1">{error}</p>}
        </div>
    );
});
NeoInput.displayName = "NeoInput";

export function NeoSelect({ className, children, error, ...props }) {
    return (
        <div className="relative w-full">
            <select
                className={cn(
                    "bg-surface rounded-xl px-4 py-2.5 shadow-neo-input outline-none focus:ring-2 focus:ring-indigo-400/50 dark:focus:ring-indigo-500/50 text-text-primary w-full transition-all appearance-none border border-transparent dark:border-white/5 cursor-pointer",
                    error && "ring-2 ring-red-400/50",
                    className
                )}
                {...props}
            >
                {children}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-gray-500">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
            </div>
            {error && <p className="mt-1 text-xs text-red-500 ml-1">{error}</p>}
        </div>
    );
}
