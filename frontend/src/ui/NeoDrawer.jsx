import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { neoTheme } from './neoTheme';
import { cn } from '../utils/cn';

export function NeoDrawer({ isOpen, onClose, title, children }) {
    const drawerRef = useRef(null);

    useEffect(() => {
        const handleEsc = (e) => {
            if (e.key === 'Escape') onClose();
        };

        if (isOpen) {
            window.addEventListener('keydown', handleEsc);
            // Lock body scroll
            document.body.style.overflow = 'hidden';
        }

        return () => {
            window.removeEventListener('keydown', handleEsc);
            document.body.style.overflow = 'auto';
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-[100] overflow-hidden" aria-labelledby="drawer-title" role="dialog" aria-modal="true">
            <div className="absolute inset-0 overflow-hidden">
                <div
                    className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm transition-opacity"
                    onClick={onClose}
                    aria-hidden="true"
                />
                <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
                    <div
                        ref={drawerRef}
                        className="pointer-events-auto w-screen max-w-md transform transition-transform duration-500 ease-in-out bg-transparent shadow-2xl"
                    >
                        <div className={cn("flex h-full flex-col overflow-y-scroll bg-app border-l border-white/40 dark:border-white/10", neoTheme.shadows.base)}>
                            {/* Header */}
                            {title && (
                                <div className="px-6 py-6 border-b border-gray-200/50 dark:border-white/5 bg-surface/80 sticky top-0 z-10 backdrop-blur-md">
                                    <div className="flex items-start justify-between">
                                        <h2 className="text-lg font-bold text-text-primary" id="drawer-title">
                                            {title}
                                        </h2>
                                        <button
                                            type="button"
                                            className="rounded-xl p-2 text-text-muted hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-indigo-500 hover:bg-white/50 dark:hover:bg-white/5 transition-colors"
                                            onClick={onClose}
                                        >
                                            <span className="sr-only">Close panel</span>
                                            <X className="h-6 w-6" aria-hidden="true" />
                                        </button>
                                    </div>
                                </div>
                            )}

                            <div className="flex-1">
                                {children}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
}
