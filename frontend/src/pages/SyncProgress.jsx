import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Terminal, Copy, Check, X, AlertTriangle, Search, Filter, Download, Zap, Activity, Info, CheckCircle, XCircle, Clock } from 'lucide-react';
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
    const [totalEmailsStored, setTotalEmailsStored] = useState(0); // Track actual count from final message
    const [searchQuery, setSearchQuery] = useState('');
    const [filterType, setFilterType] = useState('all'); // all, success, error, info, warning
    const logsEndRef = useRef(null);
    const logsTextRef = useRef(null);
    const syncStartedRef = useRef(false);
    const abortControllerRef = useRef(null);
    const onCompleteRef = useRef(onComplete);
    const onEmailAddedRef = useRef(onEmailAdded);

    // Keep latest callbacks without re-running the sync effect.
    useEffect(() => {
        onCompleteRef.current = onComplete;
    }, [onComplete]);

    useEffect(() => {
        onEmailAddedRef.current = onEmailAdded;
    }, [onEmailAdded]);

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
                    setTimeout(() => onCompleteRef.current?.(), 2000);
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
                                    
                                    // Parse final sync completion message to extract actual count
                                    // Format: "Sync completed! Stored X job application emails..."
                                    if (data.message.includes('Sync completed!') && data.message.includes('Stored')) {
                                        const match = data.message.match(/Stored\s+(\d+)\s+job\s+application\s+emails/);
                                        if (match && match[1]) {
                                            const count = parseInt(match[1], 10);
                                            setTotalEmailsStored(count);
                                        }
                                    }
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
                                    if (onEmailAddedRef.current) {
                                        onEmailAddedRef.current(emailInfo);
                                    }
                                }

                                // Handle "Skipped" stage - show prominently
                                if (data.stage === 'Skipped') {
                                    // Make sure the skipped message is visible
                                    console.log('Sync skipped - already running');
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
    }, []); // IMPORTANT: run once per mount; callbacks are read from refs

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

    const downloadLogs = () => {
        const logsText = logs.map(log => `[${log.time}] ${log.msg}`).join('\n');
        const blob = new Blob([logsText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sync-logs-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const getLogType = (msg) => {
        if (msg?.toLowerCase().includes('error') || msg?.startsWith('❌')) return 'error';
        if (msg?.toLowerCase().includes('skipped') || msg?.toLowerCase().includes('already running')) return 'warning';
        if (msg?.toLowerCase().includes('completed') || msg?.toLowerCase().includes('stored') || msg?.toLowerCase().includes('success')) return 'success';
        if (msg?.toLowerCase().includes('connecting') || msg?.toLowerCase().includes('starting')) return 'info';
        return 'info';
    };

    const getLogIcon = (type) => {
        switch (type) {
            case 'error': return <XCircle className="w-3.5 h-3.5" />;
            case 'warning': return <AlertTriangle className="w-3.5 h-3.5" />;
            case 'success': return <CheckCircle className="w-3.5 h-3.5" />;
            default: return <Info className="w-3.5 h-3.5" />;
        }
    };

    const filteredLogs = logs.filter(log => {
        const matchesSearch = !searchQuery || log.msg.toLowerCase().includes(searchQuery.toLowerCase()) || log.time.includes(searchQuery);
        const logType = getLogType(log.msg);
        const matchesFilter = filterType === 'all' || filterType === logType;
        return matchesSearch && matchesFilter;
    });

    const logStats = {
        all: logs.length,
        success: logs.filter(l => getLogType(l.msg) === 'success').length,
        error: logs.filter(l => getLogType(l.msg) === 'error').length,
        warning: logs.filter(l => getLogType(l.msg) === 'warning').length,
        info: logs.filter(l => getLogType(l.msg) === 'info').length,
    };

    return (
        <>
            <div className="fixed inset-0 z-50 flex items-center justify-center px-4 sm:px-0">
                <div className="absolute inset-0 bg-slate-500/30 backdrop-blur-sm transition-opacity" onClick={onClose} />
                <NeoCard className="max-w-lg w-full relative z-10 overflow-hidden p-8 animate-scaleIn">
                    <div className="text-center mb-8">
                        <div className="relative inline-flex items-center justify-center">
                            {stage === "Skipped" ? (
                                <div className="h-24 w-24 rounded-full shadow-neo-input flex items-center justify-center bg-amber-100 dark:bg-amber-900/30">
                                    <AlertTriangle className="h-12 w-12 text-amber-600 dark:text-amber-400" />
                                </div>
                            ) : stage === "Error" ? (
                                <div className="h-24 w-24 rounded-full shadow-neo-input flex items-center justify-center bg-red-100 dark:bg-red-900/30">
                                    <AlertCircle className="h-12 w-12 text-red-600 dark:text-red-400" />
                                </div>
                            ) : stage === "Complete" ? (
                                <div className="h-24 w-24 rounded-full shadow-neo-input flex items-center justify-center bg-green-100 dark:bg-green-900/30">
                                    <CheckCircle2 className="h-12 w-12 text-green-600 dark:text-green-400" />
                                </div>
                            ) : (
                                <div className="h-24 w-24 rounded-full shadow-neo-input flex items-center justify-center bg-slate-100 dark:bg-slate-800">
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
                                    <span className="text-2xl font-bold text-gray-800 dark:text-gray-200">{progress}%</span>
                                </div>
                            )}
                        </div>
                        <h3 className={cn(
                            "mt-6 text-xl font-bold",
                            stage === "Skipped" ? "text-amber-600 dark:text-amber-400" :
                            stage === "Error" ? "text-red-600 dark:text-red-400" :
                            stage === "Complete" ? "text-green-600 dark:text-green-400" :
                            "text-gray-800 dark:text-gray-200"
                        )}>
                            {stage}
                        </h3>
                        <p className={cn(
                            "text-sm",
                            stage === "Skipped" ? "text-amber-600 dark:text-amber-400 font-semibold" :
                            "text-gray-500 dark:text-gray-400"
                        )}>
                            {stage === "Skipped" 
                                ? "A sync is already in progress. Please wait for it to complete."
                                : "Please wait while we sync your data."
                            }
                        </p>
                        {(totalEmailsStored > 0 || emailsAdded.length > 0) && (
                            <div className="mt-4 bg-green-50 dark:bg-green-900/20 rounded-lg p-3 border border-green-200 dark:border-green-800">
                                <p className="text-sm font-semibold text-green-800 dark:text-green-200">
                                    ✓ {totalEmailsStored > 0 ? totalEmailsStored : emailsAdded.length} email{(totalEmailsStored > 0 ? totalEmailsStored : emailsAdded.length) !== 1 ? 's' : ''} stored
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Step-by-step email list */}
                    {emailsAdded.length > 0 && (
                        <div className="mb-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-700">
                            <h4 className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide mb-3">
                                Emails Being Added ({totalEmailsStored > 0 ? `${emailsAdded.length} of ${totalEmailsStored}` : emailsAdded.length})
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

                    <div className="bg-gray-900 rounded-xl p-4 font-mono text-xs h-32 overflow-y-auto custom-scrollbar shadow-inner border border-gray-800 relative">
                        {logs.length === 0 ? (
                            <div className="text-gray-500">Waiting for sync to start...</div>
                        ) : (
                            logs.map((log, i) => {
                                const isSkipped = log.msg?.toLowerCase().includes('skipped') || log.msg?.toLowerCase().includes('already running');
                                const isError = log.msg?.toLowerCase().includes('error') || log.msg?.startsWith('❌');
                                return (
                                    <div key={i} className={cn("mb-1", isSkipped && "bg-amber-900/30 px-2 py-1 rounded", isError && "bg-red-900/30 px-2 py-1 rounded")}>
                                        <span className="text-gray-500">[{log.time}]</span>{' '}
                                        <span className={cn(
                                            isSkipped ? "text-amber-400 font-bold" :
                                            isError ? "text-red-400 font-bold" :
                                            "text-green-400"
                                        )}>
                                            {log.msg}
                                        </span>
                                    </div>
                                );
                            })
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

            {/* Creative Logs Modal */}
            {showLogsModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    <div 
                        className="absolute inset-0 bg-gradient-to-br from-slate-900/80 via-indigo-900/40 to-slate-900/80 backdrop-blur-md transition-opacity" 
                        onClick={() => setShowLogsModal(false)} 
                    />
                    <div className="relative w-full max-w-7xl h-[92vh] bg-gradient-to-br from-slate-800 via-slate-800 to-slate-900 rounded-3xl shadow-2xl border border-slate-700/50 flex flex-col animate-scaleIn overflow-hidden">
                        {/* Creative Header with Gradient */}
                        <div className="relative bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 p-6 border-b border-indigo-500/30">
                            <div 
                                className="absolute inset-0 opacity-20"
                                style={{
                                    backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
                                }}
                            ></div>
                            <div className="relative flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 bg-white/10 backdrop-blur-sm rounded-xl border border-white/20">
                                        <Terminal className="w-7 h-7 text-white" />
                                    </div>
                                    <div>
                                        <h2 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-2">
                                            <Zap className="w-6 h-6 text-yellow-300 animate-pulse" />
                                            Sync Activity Logs
                                        </h2>
                                        <p className="text-indigo-200 text-sm mt-1">
                                            Real-time sync process monitoring • {logs.length} entries
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={copyLogs}
                                        className="flex items-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 backdrop-blur-sm text-white rounded-xl border border-white/20 transition-all hover:scale-105 shadow-lg"
                                        title="Copy all logs"
                                    >
                                        {copied ? (
                                            <>
                                                <Check className="w-4 h-4 text-green-300" />
                                                <span>Copied!</span>
                                            </>
                                        ) : (
                                            <>
                                                <Copy className="w-4 h-4" />
                                                <span>Copy</span>
                                            </>
                                        )}
                                    </button>
                                    <button
                                        onClick={downloadLogs}
                                        className="flex items-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 backdrop-blur-sm text-white rounded-xl border border-white/20 transition-all hover:scale-105 shadow-lg"
                                        title="Download logs"
                                    >
                                        <Download className="w-4 h-4" />
                                        <span className="hidden sm:inline">Download</span>
                                    </button>
                                    <button
                                        onClick={() => setShowLogsModal(false)}
                                        className="p-2.5 text-white/80 hover:text-white hover:bg-white/10 rounded-xl transition-all hover:scale-110"
                                        title="Close"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Stats Bar */}
                        <div className="bg-slate-800/50 border-b border-slate-700/50 p-4">
                            <div className="flex flex-wrap items-center gap-4">
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-700/50 rounded-lg border border-slate-600/50">
                                    <Activity className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm text-gray-300">Status: <span className="text-white font-semibold">{stage}</span></span>
                                </div>
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-700/50 rounded-lg border border-slate-600/50">
                                    <Clock className="w-4 h-4 text-purple-400" />
                                    <span className="text-sm text-gray-300">Progress: <span className="text-white font-semibold">{progress}%</span></span>
                                </div>
                                <div className="flex items-center gap-4 ml-auto">
                                    <button
                                        onClick={() => setFilterType('all')}
                                        className={cn(
                                            "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                                            filterType === 'all' 
                                                ? "bg-indigo-600 text-white shadow-lg scale-105" 
                                                : "bg-slate-700/50 text-gray-400 hover:bg-slate-700 border border-slate-600/50"
                                        )}
                                    >
                                        All ({logStats.all})
                                    </button>
                                    <button
                                        onClick={() => setFilterType('success')}
                                        className={cn(
                                            "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                                            filterType === 'success' 
                                                ? "bg-green-600 text-white shadow-lg scale-105" 
                                                : "bg-slate-700/50 text-gray-400 hover:bg-slate-700 border border-slate-600/50"
                                        )}
                                    >
                                        Success ({logStats.success})
                                    </button>
                                    <button
                                        onClick={() => setFilterType('error')}
                                        className={cn(
                                            "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                                            filterType === 'error' 
                                                ? "bg-red-600 text-white shadow-lg scale-105" 
                                                : "bg-slate-700/50 text-gray-400 hover:bg-slate-700 border border-slate-600/50"
                                        )}
                                    >
                                        Errors ({logStats.error})
                                    </button>
                                    <button
                                        onClick={() => setFilterType('warning')}
                                        className={cn(
                                            "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                                            filterType === 'warning' 
                                                ? "bg-amber-600 text-white shadow-lg scale-105" 
                                                : "bg-slate-700/50 text-gray-400 hover:bg-slate-700 border border-slate-600/50"
                                        )}
                                    >
                                        Warnings ({logStats.warning})
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Search Bar */}
                        <div className="p-4 bg-slate-800/30 border-b border-slate-700/50">
                            <div className="relative">
                                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="Search logs..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                                />
                                {searchQuery && (
                                    <button
                                        onClick={() => setSearchQuery('')}
                                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Logs Content - Creative Design */}
                        <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-b from-slate-900/50 to-slate-800/50">
                            <div
                                ref={logsTextRef}
                                className="bg-gradient-to-br from-gray-900 via-gray-900 to-slate-900 rounded-2xl p-6 font-mono text-sm select-text whitespace-pre-wrap break-words shadow-2xl border border-gray-800/50 min-h-full relative overflow-hidden"
                                style={{ userSelect: 'text' }}
                            >
                                {/* Animated background pattern */}
                                <div className="absolute inset-0 opacity-5">
                                    <div className="absolute inset-0" style={{
                                        backgroundImage: `linear-gradient(90deg, transparent 0%, rgba(99, 102, 241, 0.1) 50%, transparent 100%)`,
                                        backgroundSize: '200% 100%',
                                        animation: 'shimmer 3s infinite'
                                    }}></div>
                                </div>
                                
                                {filteredLogs.length === 0 ? (
                                    <div className="text-center py-12 relative z-10">
                                        <div className="text-gray-500 text-lg mb-2">
                                            {searchQuery || filterType !== 'all' ? 'No logs match your filters' : 'Waiting for sync to start...'}
                                        </div>
                                        {(searchQuery || filterType !== 'all') && (
                                            <button
                                                onClick={() => {
                                                    setSearchQuery('');
                                                    setFilterType('all');
                                                }}
                                                className="text-indigo-400 hover:text-indigo-300 text-sm mt-2"
                                            >
                                                Clear filters
                                            </button>
                                        )}
                                    </div>
                                ) : (
                                    <div className="relative z-10 space-y-1">
                                        {filteredLogs.map((log, i) => {
                                            const logType = getLogType(log.msg);
                                            const typeColors = {
                                                error: 'text-red-400 bg-red-900/20 border-red-800/50',
                                                warning: 'text-amber-400 bg-amber-900/20 border-amber-800/50',
                                                success: 'text-green-400 bg-green-900/20 border-green-800/50',
                                                info: 'text-blue-400 bg-blue-900/20 border-blue-800/50',
                                            };
                                            const colors = typeColors[logType] || typeColors.info;
                                            
                                            return (
                                                <div 
                                                    key={i} 
                                                    className={cn(
                                                        "flex items-start gap-3 p-3 rounded-lg border-l-4 transition-all hover:bg-white/5 group",
                                                        colors
                                                    )}
                                                >
                                                    <div className={cn("mt-0.5 flex-shrink-0", colors.split(' ')[0])}>
                                                        {getLogIcon(logType)}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <span className="text-gray-500 text-xs font-mono">{log.time}</span>
                                                            <span className={cn("text-xs px-2 py-0.5 rounded-full font-semibold uppercase", 
                                                                logType === 'error' && 'bg-red-900/40 text-red-300',
                                                                logType === 'warning' && 'bg-amber-900/40 text-amber-300',
                                                                logType === 'success' && 'bg-green-900/40 text-green-300',
                                                                logType === 'info' && 'bg-blue-900/40 text-blue-300'
                                                            )}>
                                                                {logType}
                                                            </span>
                                                        </div>
                                                        <p className={cn("select-text break-words", colors.split(' ')[0])}>
                                                            {log.msg}
                                                        </p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                                <div ref={logsEndRef} className="animate-pulse text-green-400 mt-4">_</div>
                            </div>
                        </div>

                        {/* Creative Footer */}
                        <div className="p-4 bg-gradient-to-r from-slate-800 via-slate-800 to-slate-900 border-t border-slate-700/50">
                            <div className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-4 text-gray-400">
                                    <div className="flex items-center gap-2">
                                        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                        <span>Live</span>
                                    </div>
                                    <span>•</span>
                                    <span>Showing {filteredLogs.length} of {logs.length} logs</span>
                                </div>
                                <div className="text-xs text-gray-500">
                                    Click and drag to select text
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
