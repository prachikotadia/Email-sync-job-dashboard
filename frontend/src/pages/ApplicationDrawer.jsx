import React, { useState, useEffect } from 'react';
import {
    Calendar,
    FileText,
    Brain,
    Edit3,
    HelpCircle,
    CheckCircle
} from 'lucide-react';
import { NeoBadge } from '../ui/NeoBadge';
import { STATUS_COLORS } from '../utils/status';
import { NeoButton } from '../ui/NeoButton';
import { NeoCard } from '../ui/NeoCard';
import { NeoDrawer } from '../ui/NeoDrawer';
import { NeoSelect } from '../ui/NeoInput';
import { NeoTooltip } from '../ui/NeoTooltip';
import { cn } from '../utils/cn';

export function ApplicationDrawer({ application, onClose, onUpdate }) {
    const [editMode, setEditMode] = useState(false);
    const [status, setStatus] = useState('');

    useEffect(() => {
        if (application) {
            setStatus(application.status);
            setEditMode(false);
        }
    }, [application]);

    if (!application) return null;

    const handleSave = () => {
        onUpdate();
        setEditMode(false);
    };

    return (
        <NeoDrawer
            isOpen={!!application}
            onClose={onClose}
            title={application.company}
        >
            <div className="p-6 space-y-6">
                {/* Header Info */}
                <div className="flex items-center space-x-4 mb-4">
                    <div className="h-16 w-16 rounded-2xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-indigo-700 dark:text-indigo-300 font-bold text-2xl shadow-neo-pressed border border-white/40 dark:border-white/5">
                        {application.company.charAt(0)}
                    </div>
                    <div>
                        <p className="text-text-secondary text-sm">Applying for</p>
                        <h3 className="text-xl font-bold text-text-primary">{application.role}</h3>
                        <p className="text-xs text-text-muted mt-1">Last activity: {application.lastUpdate || '2 days ago'}</p>
                    </div>
                </div>

                {/* Status Section */}
                <NeoCard className="p-5">
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-bold text-text-muted uppercase tracking-wider">Current Status</span>
                        {!editMode && (
                            <button onClick={() => setEditMode(true)} className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300">
                                <Edit3 className="h-4 w-4" />
                            </button>
                        )}
                    </div>
                    {editMode ? (
                        <div className="flex space-x-2">
                            <NeoSelect value={status} onChange={(e) => setStatus(e.target.value)}>
                                <option>Applied</option>
                                <option>Interview</option>
                                <option>Offer</option>
                                <option>Rejected</option>
                            </NeoSelect>
                            <NeoButton size="sm" onClick={handleSave}>Save</NeoButton>
                        </div>
                    ) : (
                        <div className="flex items-center space-x-2">
                            <NeoBadge variant={STATUS_COLORS[application.status]} className="text-sm px-3 py-1.5">{application.status}</NeoBadge>
                            <NeoTooltip content="Status automatically updated by AI based on email content.">
                                <Brain className="h-4 w-4 text-text-muted" />
                            </NeoTooltip>
                        </div>
                    )}
                </NeoCard>

                {/* AI Insight */}
                <NeoCard className={cn(
                    "border-l-4",
                    application.confidence > 0.8 ? "border-emerald-400" : "border-amber-400"
                )}>
                    <div className="flex items-start space-x-3">
                        <div className="mt-1">
                            <Brain className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                        </div>
                        <div>
                            <h4 className="text-sm font-bold text-text-primary">AI Confidence: {Math.round((application.confidence || 0.9) * 100)}%</h4>
                            <p className="text-sm text-text-secondary mt-1 leading-relaxed">
                                We marked this as reception of an interview request because the email contained phrases like "schedule a time" and "chat with the team".
                            </p>
                        </div>
                    </div>
                </NeoCard>

                {/* Activity Timeline */}
                <div>
                    <h4 className="text-sm font-bold text-text-primary mb-4 px-1">Recent Activity</h4>
                    <div className="pl-4 border-l-2 border-indigo-100 dark:border-indigo-900/40 space-y-6">
                        <div className="relative">
                            <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full bg-indigo-600 dark:bg-indigo-400 ring-4 ring-white dark:ring-surface shadow-sm"></div>
                            <NeoCard className="p-4 py-3">
                                <div className="flex justify-between items-start mb-1">
                                    <p className="text-sm font-bold text-text-primary">Email Received</p>
                                    <span className="text-xs text-text-muted">2h ago</span>
                                </div>
                                <div className="text-xs text-text-secondary bg-slate-50 dark:bg-white/5 p-2 rounded shadow-neo-input mt-2">
                                    "Hi, we'd like to move forward..."
                                </div>
                            </NeoCard>
                        </div>
                    </div>
                </div>
            </div>
        </NeoDrawer>
    );
}
