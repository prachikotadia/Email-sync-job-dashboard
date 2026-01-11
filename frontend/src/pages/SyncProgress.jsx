import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Terminal } from 'lucide-react';
import { cn } from '../utils/cn';
import { NeoCard } from '../ui/NeoCard';
import { env } from '../config/env';

export function SyncProgress({ onComplete, onClose }) {
    const [progress, setProgress] = useState(0);
    const [stage, setStage] = useState('Initializing...');
    const [logs, setLogs] = useState([]);
    const logsEndRef = useRef(null);

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
                
                // Use fetch with streaming for POST request with auth headers
                const response = await fetch(`${apiUrl}/gmail/sync`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Accept': 'text/event-stream'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
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

                                // Check if complete
                                if (data.progress === 100 || data.stage === 'Complete') {
                                    setTimeout(() => {
                                        onComplete();
                                    }, 1500);
                                } else if (data.stage === 'Error') {
                                    setTimeout(() => {
                                        onComplete();
                                    }, 2000);
                                }
                            } catch (e) {
                                console.error('Error parsing SSE data:', e);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Sync error:', error);
                addLog(`Error: ${error.message || 'Sync failed'}`);
                setStage('Error');
                setTimeout(() => {
                    onComplete();
                }, 2000);
            }
        };
        
        startSync();
    }, [onComplete]);

    return (
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
                </div>

                <div className="bg-gray-900 rounded-xl p-4 font-mono text-xs text-green-400 h-32 overflow-y-auto custom-scrollbar shadow-inner border border-gray-800">
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
            </NeoCard>
        </div>
    );
}
