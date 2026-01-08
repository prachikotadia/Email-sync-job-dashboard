import React from 'react';
import {
    Search,
    Bell,
    User,
    Menu,
    RefreshCw,
    Sun,
    Moon
} from 'lucide-react';
import { NeoButton } from '../../ui/NeoButton';
import { NeoInput } from '../../ui/NeoInput';
import { useTheme } from '../../hooks/useTheme';

export function Topbar({ onMenuClick }) {
    const { theme, toggleTheme } = useTheme();

    return (
        <header className="h-20 flex items-center justify-between px-6 sm:px-8 mt-4 mx-4 sm:mx-8 mb-8 bg-surface dark:bg-white/5 rounded-2xl shadow-neo border border-white/40 dark:border-white/5 transition-colors duration-200">
            <button
                onClick={onMenuClick}
                className="lg:hidden p-2 text-text-secondary hover:text-text-primary focus:outline-none"
            >
                <Menu className="h-6 w-6" />
            </button>
            <div className="flex-1 flex justify-between items-center">
                <div className="flex-1 flex max-w-lg ml-4 lg:ml-0">
                    <div className="relative w-full text-text-muted focus-within:text-text-primary">
                        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                            <Search className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <input
                            name="search"
                            id="search"
                            className="block w-full h-full pl-10 pr-3 py-2 border-transparent text-text-primary placeholder-text-muted focus:outline-none focus:ring-0 focus:border-transparent sm:text-sm bg-transparent"
                            placeholder="Search applications..."
                            type="search"
                        />
                    </div>
                </div>
                <div className="ml-4 flex items-center md:ml-6 space-x-4">
                    {/* Theme Toggle */}
                    <NeoButton
                        variant="secondary"
                        className="p-2 rounded-xl"
                        onClick={toggleTheme}
                        title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                    >
                        {theme === 'light' ? (
                            <Moon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                        ) : (
                            <Sun className="h-5 w-5 text-amber-500" />
                        )}
                    </NeoButton>

                    <NeoButton variant="secondary" className="p-2 rounded-xl">
                        <RefreshCw className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    </NeoButton>

                    <button className="bg-surface dark:bg-white/5 p-2 rounded-xl text-text-secondary hover:text-text-primary focus:outline-none shadow-neo active:shadow-neo-pressed transition-all relative border border-transparent dark:border-white/5">
                        <span className="sr-only">View notifications</span>
                        <Bell className="h-6 w-6" aria-hidden="true" />
                        <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-black"></span>
                    </button>

                    {/* Profile dropdown */}
                    <div className="relative ml-2">
                        <div className="flex items-center">
                            <div className="h-10 w-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-indigo-600 dark:text-indigo-300 font-bold shadow-neo border border-white/40 dark:border-white/10">
                                JD
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}
