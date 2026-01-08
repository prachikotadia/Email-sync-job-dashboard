import React from 'react';
import { cn } from '../utils/cn';

export function NeoBadge({ children, variant = 'default', className, confidence, ...props }) {
    const variants = {
        default: "text-text-secondary bg-surface ring-1 ring-gray-200 dark:ring-gray-700",
        primary: "text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/30 ring-1 ring-indigo-100 dark:ring-indigo-800",
        success: "text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/30 ring-1 ring-emerald-100 dark:ring-emerald-800",
        warning: "text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 ring-1 ring-amber-100 dark:ring-amber-800",
        danger: "text-red-600 dark:text-red-300 bg-red-50 dark:bg-red-900/30 ring-1 ring-red-100 dark:ring-red-800",
        // Confidence variants
        high: "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 ring-1 ring-emerald-200 dark:ring-emerald-800", // > 0.8
        medium: "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 ring-1 ring-amber-200 dark:ring-amber-800", // 0.6 - 0.8
        low: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/30 ring-1 ring-red-200 dark:ring-red-800 animate-pulse", // < 0.6
    };

    let selectedVariant = variant;
    if (confidence !== undefined) {
        if (confidence >= 0.8) selectedVariant = 'high';
        else if (confidence >= 0.6) selectedVariant = 'medium';
        else selectedVariant = 'low';
    }

    return (
        <span
            className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-medium shadow-sm",
                variants[selectedVariant],
                className
            )}
            {...props}
        >
            {confidence !== undefined && (
                <span className={cn("mr-1.5 h-1.5 w-1.5 rounded-full",
                    confidence >= 0.8 ? "bg-emerald-500" :
                        confidence >= 0.6 ? "bg-amber-500" : "bg-red-500"
                )} />
            )}
            {children}
            {confidence !== undefined && (
                <span className="ml-1 opacity-75">
                    {Math.round(confidence * 100)}%
                </span>
            )}
        </span>
    );
}
