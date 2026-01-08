import React, { useState } from 'react';
import { cn } from '../utils/cn';

export function NeoTooltip({ content, children }) {
    const [isVisible, setIsVisible] = useState(false);

    return (
        <div
            className="relative inline-block"
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
            onFocus={() => setIsVisible(true)}
            onBlur={() => setIsVisible(false)}
        >
            {children}
            {isVisible && (
                <div className="absolute z-50 px-3 py-2 text-xs font-medium text-white bg-slate-800 dark:bg-black rounded-lg shadow-xl -top-10 left-1/2 transform -translate-x-1/2 w-max max-w-xs animate-fadeIn border border-white/10">
                    <div className="absolute w-2 h-2 bg-slate-800 dark:bg-black transform rotate-45 left-1/2 -translate-x-1/2 -bottom-1 border-r border-b border-white/10"></div>
                    {content}
                </div>
            )}
        </div>
    );
}
