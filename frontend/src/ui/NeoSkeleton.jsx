import React from 'react';
import { cn } from '../utils/cn';

export function NeoSkeleton({ rows = 5, columns = 4, density = 'comfortable', className }) {
    return (
        <div className={cn("space-y-4 p-6 animate-pulse", className)}>
            {[...Array(rows)].map((_, i) => (
                <div key={i} className={cn("flex space-x-4", density === 'compact' ? 'py-1' : 'py-3')}>
                    <div className="h-10 w-10 bg-black/5 dark:bg-white/5 rounded-full"></div>
                    <div className="flex-1 space-y-2 py-1">
                        <div className="h-4 bg-black/5 dark:bg-white/5 rounded w-3/4"></div>
                        <div className="h-4 bg-black/5 dark:bg-white/5 rounded w-1/2"></div>
                    </div>
                </div>
            ))}
        </div>
    );
}
