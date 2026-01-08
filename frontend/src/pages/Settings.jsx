import React, { useState, useEffect } from 'react';
import { Server, Shield, Save, Monitor, AlertTriangle, Moon, Sun } from 'lucide-react';
import { checkHealth } from '../services/api';
import { useToast } from '../context/ToastContext';
import { useTheme } from '../hooks/useTheme';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoInput } from '../ui/NeoInput';
import { NeoBadge } from '../ui/NeoBadge';

export default function Settings() {
    const { addToast } = useToast();
    const { theme, toggleTheme } = useTheme();
    const [health, setHealth] = useState({ emailService: null, appService: null });
    const [ghostedThreshold, setGhostedThreshold] = useState(14);
    const [isConnected, setIsConnected] = useState(true);

    useEffect(() => {
        const fetchHealth = async () => {
            const status = await checkHealth();
            setHealth(status);
        };
        fetchHealth();
    }, []);

    const handleDisconnect = () => {
        if (window.confirm("Are you sure you want to disconnect your Google Account? You will stop receiving sync updates.")) {
            setIsConnected(false);
            addToast("Details disconnected successfully", "success");
        }
    };

    const handleConnect = () => {
        setIsConnected(true);
        addToast("Connected to Google Account", "success");
    };

    const handleSave = () => {
        localStorage.setItem('ghostedThreshold', ghostedThreshold);
        addToast("Preferences saved successfully", "success");
    };

    return (
        <div className="max-w-3xl mx-auto space-y-8 pb-12">
            <div className="flex justify-between items-start">
                <div>
                    <h1 className="text-3xl font-bold text-text-primary tracking-tight">Settings</h1>
                    <p className="mt-1 text-sm text-text-secondary">System configuration and preferences</p>
                </div>
                <NeoBadge className="text-sm px-3 py-1">
                    <Shield className="h-3 w-3 mr-1" /> Role: Editor
                </NeoBadge>
            </div>

            {/* Account & Security */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Shield className="h-5 w-5 mr-2 text-text-muted" />
                        Account & Permissions
                    </h3>
                </div>
                <div className="p-6 space-y-6">
                    {isConnected ? (
                        <div className="flex items-center justify-between animate-fadeIn">
                            <div className="flex items-center">
                                <div className="h-10 w-10 rounded-xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold mr-4 shadow-neo-pressed border border-white/40 dark:border-white/5">
                                    J
                                </div>
                                <div>
                                    <p className="text-sm font-bold text-text-primary">Connected Account</p>
                                    <p className="text-sm text-text-secondary">john.doe@gmail.com</p>
                                </div>
                            </div>
                            <NeoButton
                                variant="ghost"
                                onClick={handleDisconnect}
                                className="text-sm px-3 py-1.5 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                            >
                                Disconnect
                            </NeoButton>
                        </div>
                    ) : (
                        <div className="text-center py-4 animate-fadeIn">
                            <p className="text-text-secondary mb-4">No account connected.</p>
                            <NeoButton onClick={handleConnect}>
                                Connect Google Account
                            </NeoButton>
                        </div>
                    )}

                    {isConnected && (
                        <div className="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-4 border border-amber-100/50 dark:border-amber-800/30 shadow-sm">
                            <div className="flex">
                                <AlertTriangle className="h-5 w-5 text-amber-500 dark:text-amber-400 mt-0.5" />
                                <div className="ml-3">
                                    <h3 className="text-sm font-bold text-amber-800 dark:text-amber-300">Permission Scope: Read-Only</h3>
                                    <div className="mt-2 text-sm text-amber-700 dark:text-amber-400">
                                        <p>
                                            JobPulse AI only has access to view email subjects and snippets.
                                            We cannot delete, send, or modify your emails.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </NeoCard>

            {/* Theme & Appearance */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Monitor className="h-5 w-5 mr-2 text-text-muted" />
                        Appearance
                    </h3>
                </div>
                <div className="p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-bold text-text-primary">Theme Mode</p>
                            <p className="text-xs text-text-secondary mt-1">
                                Currently using <span className="font-semibold capitalize">{theme}</span> mode
                            </p>
                        </div>
                        <div className="flex items-center bg-app dark:bg-black/20 p-1.5 rounded-xl border border-white/50 dark:border-white/5">
                            <button
                                onClick={() => theme === 'dark' && toggleTheme()}
                                className={`p-2 rounded-lg transition-all flex items-center space-x-2 ${theme === 'light' ? 'bg-surface shadow-sm text-indigo-600' : 'text-text-muted hover:text-text-secondary'}`}
                            >
                                <Sun className="h-4 w-4" />
                                <span className="text-xs font-medium">Light</span>
                            </button>
                            <button
                                onClick={() => theme === 'light' && toggleTheme()}
                                className={`p-2 rounded-lg transition-all flex items-center space-x-2 ${theme === 'dark' ? 'bg-indigo-500/10 shadow-sm text-indigo-400' : 'text-text-muted hover:text-text-secondary'}`}
                            >
                                <Moon className="h-4 w-4" />
                                <span className="text-xs font-medium">Dark</span>
                            </button>
                        </div>
                    </div>
                </div>
            </NeoCard>

            {/* Application Logic */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Monitor className="h-5 w-5 mr-2 text-text-muted" />
                        Preferences
                    </h3>
                </div>
                <div className="p-6 space-y-6">
                    <div className="max-w-xs">
                        <label htmlFor="ghosted" className="block text-sm font-medium text-text-primary mb-2">
                            Ghosted Threshold (Days)
                        </label>
                        <p className="text-xs text-text-secondary mb-3">Auto-mark as 'Ghosted' if no contact after this many days.</p>
                        <div className="flex items-center">
                            <NeoInput
                                type="number"
                                id="ghosted"
                                value={ghostedThreshold}
                                onChange={(e) => setGhostedThreshold(e.target.value)}
                            />
                        </div>
                    </div>
                </div>
                <div className="px-6 py-4 bg-slate-100/50 dark:bg-white/5 text-right border-t border-gray-200/50 dark:border-white/5">
                    <NeoButton
                        onClick={handleSave}
                        className="inline-flex items-center"
                    >
                        <Save className="h-4 w-4 mr-2" />
                        Save Preferences
                    </NeoButton>
                </div>
            </NeoCard>

            {/* System Health */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Server className="h-5 w-5 mr-2 text-text-muted" />
                        System Health
                    </h3>
                </div>
                <div className="p-6 space-y-4">
                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm ${health.emailService ? 'bg-green-500' : health.emailService === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">Email AI Service</p>
                                <p className="text-xs text-text-secondary">Processing and sync engine</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.emailService ? 'success' : 'default'}>
                            {health.emailService ? 'Operational' : health.emailService === false ? 'Offline' : 'Checking...'}
                        </NeoBadge>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm ${health.appService ? 'bg-green-500' : health.appService === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">Application Service</p>
                                <p className="text-xs text-text-secondary">Main backend API</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.appService ? 'success' : 'default'}>
                            {health.appService ? 'Operational' : health.appService === false ? 'Offline' : 'Checking...'}
                        </NeoBadge>
                    </div>
                </div>
            </NeoCard>

            <div className="text-center text-xs text-text-muted mt-8 mb-4">
                <p>JobPulse AI v1.0.0 (Beta)</p>
                <p>Environment: {import.meta.env.MODE || 'Development'}</p>
            </div>
        </div>
    );
}
