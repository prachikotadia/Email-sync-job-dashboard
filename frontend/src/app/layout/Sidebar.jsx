import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Briefcase,
    FileText,
    Settings,
    LogOut,
    X,
    Download
} from 'lucide-react';
import { cn } from '../../utils/cn';

export function Sidebar({ isOpen, onClose }) {
    const navigation = [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Applications', href: '/applications', icon: Briefcase },
        { name: 'Resumes', href: '/resumes', icon: FileText },
        { name: 'Export Data', href: '/export', icon: Download },
        { name: 'Settings', href: '/settings', icon: Settings },
    ];

    return (
        <>
            <div
                className={cn(
                    "fixed inset-0 z-40 bg-slate-500/30 dark:bg-black/50 backdrop-blur-sm lg:hidden transition-opacity",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={onClose}
            />

            <div className={cn(
                "fixed inset-y-0 left-0 z-50 w-64 bg-surface shadow-neo transform transition-transform duration-300 ease-out lg:translate-x-0 lg:static lg:inset-0 sm:m-4 rounded-2xl border border-white/40 dark:border-white/5",
                isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
            )}>
                <div className="flex items-center justify-between h-20 px-6 border-b border-white/20 dark:border-white/5">
                    <div className="flex items-center space-x-3">
                        <div className="h-10 w-10 bg-indigo-600 dark:bg-indigo-500 rounded-xl shadow-neo-button flex items-center justify-center">
                            <span className="text-white font-bold text-xl">JP</span>
                        </div>
                        <span className="text-xl font-bold text-text-primary tracking-tight">JobPulse</span>
                    </div>
                    <button onClick={onClose} className="lg:hidden p-2 text-text-secondary hover:text-text-primary">
                        <X className="h-6 w-6" />
                    </button>
                </div>

                <nav className="p-4 space-y-2 mt-4">
                    {navigation.map((item) => (
                        <NavLink
                            key={item.name}
                            to={item.href}
                            onClick={() => onClose()}
                            className={({ isActive }) => cn(
                                "flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200",
                                isActive
                                    ? "bg-surface shadow-neo-pressed text-indigo-600 dark:text-indigo-400"
                                    : "text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5"
                            )}
                        >
                            <item.icon className="mr-3 h-5 w-5" />
                            {item.name}
                        </NavLink>
                    ))}
                </nav>

                <div className="absolute bottom-0 w-full p-4 border-t border-white/20 dark:border-white/5">
                    <button className="flex items-center w-full px-4 py-3 text-sm font-medium text-red-500 rounded-xl hover:bg-red-50 dark:hover:bg-red-900/20 hover:shadow-neo transition-all">
                        <LogOut className="mr-3 h-5 w-5" />
                        Sign Out
                    </button>
                </div>
            </div>
        </>
    );
}
