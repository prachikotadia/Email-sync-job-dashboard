import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Terminal, Copy, Check, X } from 'lucide-react';
import { cn } from '../utils/cn';
import { NeoCard } from '../ui/NeoCard';
import { env } from '../config/env';

export function SyncProgress({ onComplete, onClose, onEmailAdded }) {
    const [progress, setProgress] = useState(0);
    const [stage, setStage] = useState('Initializing...');
    const [logs, setLogs] = useState([]);
    const [showLogsModal, setShowLogsModal] = useState(false);
    const [copied, setCopied] = useState(false);
    const [emailsAdded, setEmailsAdded] = useState([]);
    const logsEndRef = useRef(null);
    const logsTextRef = useRef(null);
    const syncStartedRef = useRef(false);
    const abortControllerRef = useRef(null);

    const addLog = (msg) => {
        const time = new Date().toLocaleTimeString();
        setLogs(prev => [...prev, { time, msg }]);
        // Auto-scroll to bottom
        setTimeout(() => {
            if (logsEndRef.current) {
                logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
            }
        }, 100);
    };

    useEffect(() => {
        // Prevent duplicate syncs
        if (syncStartedRef.current) {
            console.log('Sync already started, skipping...');
            return;
        }
        syncStartedRef.current = true;

        // Start sync process with Server-Sent Events
        const startSync = async () => {
            try {
                const token = localStorage.getItem('auth_access_token');
                if (!token) {
                    addLog('Error: No authentication token found');
                    setStage('Error');
                    setTimeout(() => onComplete(), 2000);
                    return;
                }

                const apiUrl = env.API_GATEWAY_URL || 'http://localhost:8000';
                
                // Create abort controller for cleanup
                abortControllerRef.current = new AbortController();
                
                // Use fetch with streaming for POST request with auth headers
                addLog(`Connecting to ${apiUrl}/gmail/sync...`);
                const response = await fetch(`${apiUrl}/gmail/sync`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Accept': 'text/event-stream'
                    },
                    signal: abortControllerRef.current.signal
                });

                if (!response.ok) {
                    const errorText = await response.text().catch(() => 'Unknown error');
                    addLog(`HTTP error! status: ${response.status}`);
                    addLog(`Error details: ${errorText}`);
                    throw new Error(`HTTP ${response.status}: ${errorText || 'Sync failed'}`);
                }
                
                addLog('Connected! Starting sync...');

                if (!response.body) {
                    throw new Error('Response body is null. Cannot read sync stream.');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    let readResult;
                    try {
                        readResult = await reader.read();
                    } catch (readError) {
                        // Handle abort errors gracefully
                        if (readError.name === 'AbortError' || readError.message?.includes('aborted')) {
                            console.log('Stream reading aborted (expected during cleanup)');
                            break;
                        }
                        throw readError; // Re-throw unexpected errors
                    }
                    
                    const { done, value } = readResult;
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep incomplete line in buffer

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (data.message) {
                                    addLog(data.message);
                                }
                                if (data.progress !== undefined) {
                                    setProgress(data.progress);
                                }
                                if (data.stage) {
                                    setStage(data.stage);
                                }
                                
                                // Handle email data updates
                                if (data.email_data) {
                                    const emailInfo = data.email_data;
                                    setEmailsAdded(prev => [...prev, emailInfo]);
                                    // Notify parent component to refresh applications
                                    if (onEmailAdded) {
                                        onEmailAdded(emailInfo);
                                    }
                                }

                                // Check if complete - DON'T auto-close, let user close manually
                                // if (data.progress === 100 || data.stage === 'Complete') {
                                //     setTimeout(() => {
                                //         onComplete();
                                //     }, 1500);
                                // } else if (data.stage === 'Error') {
                                //     setTimeout(() => {
                                //         onComplete();
                                //     }, 2000);
                                // }
                            } catch (e) {
                                console.error('Error parsing SSE data:', e);
                            }
                        }
                    }
                }
            } catch (error) {
                // Ignore AbortError - it's expected when component unmounts or user cancels
                if (error.name === 'AbortError' || error.message?.includes('aborted')) {
                    console.log('Sync aborted (expected during cleanup)');
                    return;
                }
                
                console.error('Sync error:', error);
                const errorMsg = error.message || 'Sync failed';
                addLog(`❌ Error: ${errorMsg}`);
                addLog('Please check the logs above for details.');
                setStage('Error');
                setProgress(0);
                // Don't auto-close on error - let user see the logs
                // setTimeout(() => {
                //     onComplete();
                // }, 2000);
            }
        };
        
        startSync();
        
        // Cleanup function
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            syncStartedRef.current = false;
        };
    }, [onComplete]);

    const copyLogs = async () => {
        const logsText = logs.map(log => `[${log.time}] ${log.msg}`).join('\n');
        try {
            await navigator.clipboard.writeText(logsText);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy logs:', err);
            // Fallback: select text
            if (logsTextRef.current) {
                const range = document.createRange();
                range.selectNodeContents(logsTextRef.current);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
            }
        }
    };

    return (
        <>
            <div className="fixed inset-0 z-50 flex items-center justify-center px-4 sm:px-0">
                <div className="absolute inset-0 bg-slate-500/30 backdrop-blur-sm transition-opacity" onClick={onClose} />
                <NeoCard className="max-w-lg w-full relative z-10 overflow-hidden p-8 animate-scaleIn">
                    <div className="text-center mb-8">
                        <div className="relative inline-flex items-center justify-center">
                            <div className="h-24 w-24 rounded-full shadow-neo-input flex items-center justify-center bg-slate-100">
                                <svg className="w-24 h-24 absolute transform -rotate-90">
                                    <circle
                                        className="text-transparent"
                                        strokeWidth="6"
                                        stroke="currentColor"
                                        fill="transparent"
                                        r="44"
                                        cx="48"
                                        cy="48"
                                    />
                                    <circle
                                        className="text-indigo-600 transition-all duration-300 ease-linear shadow-lg"
                                        strokeWidth="6"
                                        strokeDasharray={276}
                                        strokeDashoffset={276 - (276 * progress) / 100}
                                        strokeLinecap="round"
                                        stroke="currentColor"
                                        fill="transparent"
                                        r="44"
                                        cx="48"
                                        cy="48"
                                    />
                                </svg>
                                <span className="text-2xl font-bold text-gray-800">{progress}%</span>
                            </div>
                        </div>
                        <h3 className="mt-6 text-xl font-bold text-gray-800">{stage}</h3>
                        <p className="text-sm text-gray-500">Please wait while we sync your data.</p>
                        {emailsAdded.length > 0 && (
                            <div className="mt-4 bg-green-50 dark:bg-green-900/20 rounded-lg p-3 border border-green-200 dark:border-green-800">
                                <p className="text-sm font-semibold text-green-800 dark:text-green-200">
                                    ✓ {emailsAdded.length} email{emailsAdded.length !== 1 ? 's' : ''} stored
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Step-by-step email list */}
                    {emailsAdded.length > 0 && (
                        <div className="mb-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-700">
                            <h4 className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide mb-3">
                                Emails Being Added ({emailsAdded.length})
                            </h4>
                            <div className="space-y-2">
                                {emailsAdded.slice().reverse().map((email, i) => (
                                    <div 
                                        key={i} 
                                        className="flex items-center justify-between p-2 bg-white dark:bg-slate-700 rounded-lg border border-green-200 dark:border-green-800 animate-slideInRight"
                                        style={{ animationDelay: `${i * 50}ms` }}
                                    >
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">
                                                {email.company_name || 'New Application'}
                                            </p>
                                            <p className="text-xs text-slate-600 dark:text-slate-400 truncate">
                                                {email.role || 'Job Application'} • {email.status || 'Applied'}
                                            </p>
                                        </div>
                                        <div className="ml-2 flex-shrink-0">
                                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="bg-gray-900 rounded-xl p-4 font-mono text-xs text-green-400 h-32 overflow-y-auto custom-scrollbar shadow-inner border border-gray-800 relative">
                        {logs.length === 0 ? (
                            <div className="text-gray-500">Waiting for sync to start...</div>
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className="mb-1">
                                    <span className="text-gray-500">[{log.time}]</span> <span className="text-green-400">{log.msg}</span>
                                </div>
                            ))
                        )}
                        <div ref={logsEndRef} className="animate-pulse">_</div>
                    </div>

                    <div className="mt-4 flex gap-2 justify-end">
                        <button
                            onClick={() => setShowLogsModal(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-neo-button"
                        >
                            <Terminal className="w-4 h-4" />
                            View Full Logs
                        </button>
                        <button
                            onClick={onClose}
                            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors shadow-neo-button"
                        >
                            Close
                        </button>
                    </div>
                </NeoCard>
            </div>

            {/* Large Logs Modal */}
            {showLogsModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    <div 
                        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity" 
                        onClick={() => setShowLogsModal(false)} 
                    />
                    <div className="relative w-full max-w-6xl h-[90vh] bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col animate-scaleIn">
                        {/* Header */}
                        <div className="flex items-center justify-between p-6 border-b border-slate-700">
                            <div className="flex items-center gap-3">
                                <Terminal className="w-6 h-6 text-green-400" />
                                <h2 className="text-2xl font-bold text-white">Sync Logs</h2>
                                <span className="text-sm text-gray-400">({logs.length} entries)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={copyLogs}
                                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-lg"
                                    title="Copy all logs"
                                >
                                    {copied ? (
                                        <>
                                            <Check className="w-4 h-4" />
                                            <span>Copied!</span>
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="w-4 h-4" />
                                            <span>Copy All</span>
                                        </>
                                    )}
                                </button>
                                <button
                                    onClick={() => setShowLogsModal(false)}
                                    className="p-2 text-gray-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                                    title="Close"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                        </div>

                        {/* Logs Content - Selectable */}
                        <div className="flex-1 overflow-y-auto p-6">
                            <div
                                ref={logsTextRef}
                                className="bg-gray-900 rounded-xl p-6 font-mono text-sm text-green-400 select-text whitespace-pre-wrap break-words shadow-inner border border-gray-800 min-h-full"
                                style={{ userSelect: 'text' }}
                            >
                                {logs.length === 0 ? (
                                    <div className="text-gray-500">Waiting for sync to start...</div>
                                ) : (
                                    logs.map((log, i) => (
                                        <div key={i} className="mb-2 select-text">
                                            <span className="text-gray-500">[{log.time}]</span>{' '}
                                            <span className="text-green-400">{log.msg}</span>
                                        </div>
                                    ))
                                )}
                                <div ref={logsEndRef} className="animate-pulse text-green-400">_</div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="p-4 border-t border-slate-700 bg-slate-800/50">
                            <div className="flex items-center justify-between text-sm text-gray-400">
                                <div>
                                    Status: <span className="text-white font-semibold">{stage}</span>
                                    {' • '}
                                    Progress: <span className="text-white font-semibold">{progress}%</span>
                                </div>
                                <div className="text-xs">
                                    Click and drag to select text, or use "Copy All" button
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
