import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Terminal } from 'lucide-react';
import { cn } from '../utils/cn';
import { NeoCard } from '../ui/NeoCard';

export function SyncProgress({ onComplete, onClose }) {
    const [progress, setProgress] = useState(0);
    const [stage, setStage] = useState('Fetching emails...');
    const [logs, setLogs] = useState([]);

    const addLog = (msg) => {
        setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg }]);
    };

    useEffect(() => {
        const interval = setInterval(() => {
            setProgress(p => {
                if (p >= 100) {
                    clearInterval(interval);
                    setStage('Complete');
                    addLog('Sync completed successfully.');
                    setTimeout(onComplete, 1000);
                    return 100;
                }

                // Simulation logic
                if (p === 10) { setStage('Processing emails...'); addLog('Fetched 50 emails from Gmail API'); }
                if (p === 40) { setStage('Analyzing with AI...'); addLog('AI classifying applications...'); }
                if (p === 70) { setStage('Updating Database...'); addLog('Upserting job records to DB...'); }

                return p + 5;
            });
        }, 300);
        return () => clearInterval(interval);
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
                    {logs.map((log, i) => (
                        <div key={i} className="mb-1">
                            <span className="text-gray-500">[{log.time}]</span> {log.msg}
                        </div>
                    ))}
                    <div className="animate-pulse">_</div>
                </div>
            </NeoCard>
        </div>
    );
}
