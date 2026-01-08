import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { cn } from '../utils/cn';

export function NeoModal({ isOpen, onClose, title, children }) {
    useEffect(() => {
        const handleEsc = (e) => {
            if (e.key === 'Escape') onClose();
        };
        if (isOpen) {
            window.addEventListener('keydown', handleEsc);
            document.body.style.overflow = 'hidden';
        }
        return () => {
            window.removeEventListener('keydown', handleEsc);
            document.body.style.overflow = 'auto';
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-[100] overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
            <div className="flex min-h-screen items-center justify-center p-4 text-center sm:p-0">
                <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm transition-opacity" aria-hidden="true" onClick={onClose} />

                <div className="relative transform overflow-hidden rounded-2xl bg-surface text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-lg border border-white/40 dark:border-white/10">
                    <div className="bg-surface px-4 pt-5 pb-4 sm:p-6 sm:pb-4 border-b border-gray-100 dark:border-white/5">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-bold leading-6 text-text-primary" id="modal-title">
                                {title}
                            </h3>
                            <button
                                type="button"
                                className="rounded-lg p-1 text-text-muted hover:text-text-primary focus:outline-none hover:bg-gray-200 dark:hover:bg-white/10 transition-colors"
                                onClick={onClose}
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>
                    </div>
                    <div className="bg-app/50 px-4 py-5 sm:p-6">
                        {children}
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
}
