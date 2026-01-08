import React, { useEffect, useState } from 'react';
import { cn } from '../utils/cn';
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { neoTheme } from './neoTheme';

export function NeoToast({ message, type = 'info', onClose, duration = 3000 }) {
    const [visible, setVisible] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setVisible(false);
            if (onClose) setTimeout(onClose, 300); // Wait for exit animation
        }, duration);
        return () => clearTimeout(timer);
    }, [duration, onClose]);

    const icons = {
        success: <CheckCircle className="h-5 w-5 text-emerald-500" />,
        error: <AlertCircle className="h-5 w-5 text-red-500" />,
        warning: <AlertTriangle className="h-5 w-5 text-amber-500" />,
        info: <Info className="h-5 w-5 text-indigo-500" />
    };

    if (!visible) return null; // Or handle actual unmounting in parent

    return (
        <div className={cn(
            "flex items-center p-4 rounded-xl bg-surface border border-white/60 dark:border-white/5 mb-3 animate-slideInRight",
            neoTheme.shadows.base
        )}>
            <div className="flex-shrink-0 mr-3">
                {icons[type]}
            </div>
            <div className="flex-1 text-sm font-medium text-text-primary">
                {message}
            </div>
            <button
                onClick={() => setVisible(false)}
                className="ml-3 text-text-muted hover:text-text-primary focus:outline-none"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    );
}
