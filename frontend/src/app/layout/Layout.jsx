import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { Outlet } from 'react-router-dom';
import { useDemoMode } from '../../hooks/useDemoMode';
import { AlertCircle } from 'lucide-react';

export function Layout() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const { isDemoMode } = useDemoMode();

    return (
        <div className="flex h-screen bg-app overflow-hidden">
            <Sidebar
                isOpen={sidebarOpen}
                onClose={() => setSidebarOpen(false)}
            />

            <div className="flex-1 flex flex-col overflow-hidden w-full transition-colors duration-200">
                {isDemoMode && (
                    <div className="bg-amber-500/10 dark:bg-amber-900/40 border-b border-amber-500/20 text-amber-700 dark:text-amber-400 px-4 py-1.5 text-xs font-medium flex items-center justify-center animate-slideUp">
                        <AlertCircle className="h-3.5 w-3.5 mr-2" />
                        Demo Mode - Backend Disconnected
                    </div>
                )}
                <Topbar onMenuClick={() => setSidebarOpen(true)} />

                <main className="flex-1 overflow-x-hidden overflow-y-auto bg-app">
                    <div className="container mx-auto px-4 sm:px-8 pb-10">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
}
