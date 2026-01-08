import React from 'react';
import { cn } from '../utils/cn';
import { Loader2 } from 'lucide-react';

export function NeoButton({
    children,
    className,
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled = false,
    icon: Icon,
    ...props
}) {
    const variants = {
        primary: "bg-indigo-600 dark:bg-indigo-500 text-white shadow-neo-button hover:brightness-110 active:shadow-neo-button-active",
        secondary: "bg-surface text-text-primary shadow-neo hover:brightness-95 dark:hover:brightness-110 active:shadow-neo-pressed",
        ghost: "bg-transparent text-text-secondary hover:bg-black/5 dark:hover:bg-white/5 shadow-none",
        danger: "bg-red-500 text-white shadow-[6px_6px_14px_rgba(239,68,68,0.35),_-6px_-6px_14px_rgba(255,255,255,0.65)] hover:brightness-105 active:shadow-[inset_6px_6px_12px_rgba(0,0,0,0.18)]"
    };

    const sizes = {
        sm: "px-3 py-1.5 text-xs",
        md: "px-4 py-2 text-sm",
        lg: "px-6 py-3 text-base"
    };

    return (
        <button
            disabled={disabled || loading}
            className={cn(
                "rounded-xl font-medium transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-400/50 flex items-center justify-center",
                variants[variant],
                sizes[size],
                (disabled || loading) && "opacity-60 cursor-not-allowed shadow-none",
                className
            )}
            {...props}
        >
            {loading && <Loader2 className="animate-spin mr-2 h-4 w-4" />}
            {!loading && Icon && <Icon className="mr-2 h-4 w-4" />}
            {children}
        </button>
    );
}
