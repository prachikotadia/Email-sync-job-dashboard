import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useParams, useNavigate } from 'react-router-dom';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useRef } from 'react';
import {
    Search,
    Filter,
    MoreHorizontal,
    Download,
    AlertTriangle,
    Trash2,
    Calendar,
    Brain
} from 'lucide-react';
import { NeoBadge } from '../ui/NeoBadge';
import { ApplicationDrawer } from './ApplicationDrawer';
import { STATUS_COLORS } from '../utils/status';
import { useToast } from '../context/ToastContext';
import { useApplications } from '../hooks/useApplications';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoInput, NeoSelect } from '../ui/NeoInput';
import { NeoTable } from '../ui/NeoTable';
import { NeoModal } from '../ui/NeoModal';
import { NeoTooltip } from '../ui/NeoTooltip';

export default function Applications() {
    const [searchParams, setSearchParams] = useSearchParams();
    const { id } = useParams();
    const navigate = useNavigate();
    const { addToast } = useToast();
    const searchInputRef = useRef(null);

    useKeyboardShortcuts({
        '/': () => searchInputRef.current?.focus()
    });

    // Hooks
    const filterStatus = searchParams.get('status') || 'All';
    const searchQuery = searchParams.get('q') || '';
    const { applications, loading } = useApplications({ status: filterStatus });

    const [selectedApp, setSelectedApp] = useState(null);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [showAddModal, setShowAddModal] = useState(false);

    // Deep Linking Effect
    useEffect(() => {
        if (id && applications.length > 0) {
            const app = applications.find(a => a.id.toString() === id);
            if (app) setSelectedApp(app);
        }
    }, [id, applications]);

    const closeDrawer = () => {
        setSelectedApp(null);
        if (id) navigate('/applications');
    };

    const openDrawer = (app) => {
        setSelectedApp(app);
        navigate(`/applications/${app.id}`);
    };

    // Filtering - also filter out invalid statuses
    const filteredApps = useMemo(() => {
        // Valid job application statuses
        const validStatuses = ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer", 
                              "Screening", "Interview (R1)", "Interview (R2)", "Interview (Final)",
                              "Offer", "Accepted", "Hired"];
        
        return applications.filter(app => {
            // First, filter out invalid/Unknown statuses
            const status = app.status || "";
            const isValidStatus = validStatuses.includes(status) || 
                                 status.includes("Interview") || 
                                 ["Offer", "Accepted", "Hired"].includes(status);
            if (!isValidStatus || status === "Unknown") {
                return false; // Don't show invalid statuses
            }
            
            // Then apply user filters
            const matchesStatus = filterStatus === 'All' || app.status === filterStatus;
            let matchesSearch = true;
            if (searchQuery) {
                const lowerQuery = searchQuery.toLowerCase();
                const companyName = (app.company || app.company_name || '').toLowerCase();
                const roleName = (app.role || app.role_title || '').toLowerCase();
                matchesSearch =
                    companyName.includes(lowerQuery) ||
                    roleName.includes(lowerQuery);
            }
            return matchesStatus && matchesSearch;
        });
    }, [applications, filterStatus, searchQuery]);

    const handleFilterChange = (key, value) => {
        setSearchParams(prev => {
            if (value === 'All' && key === 'status') prev.delete(key);
            else prev.set(key, value);
            return prev;
        });
    };

    const handleBulkAction = (action) => {
        addToast(`${action} ${selectedIds.size} applications successfully`, 'success');
        setSelectedIds(new Set());
    };

    const handleSave = () => {
        addToast("Application Saved", "success");
        setShowAddModal(false);
    };

    // Table Config
    const columns = [
        {
            key: 'company',
            header: 'Company',
            sortable: true,
            render: (app) => {
                const companyName = app.company || app.company_name || 'Unknown';
                const firstLetter = companyName && companyName.length > 0 ? companyName.charAt(0).toUpperCase() : '?';
                return (
                    <div className="flex items-center">
                        <div className="h-9 w-9 rounded-xl bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center text-indigo-700 dark:text-indigo-400 font-bold shadow-neo-pressed mr-3">
                            {firstLetter}
                        </div>
                        <div>
                            <div className="font-bold text-text-primary">{companyName}</div>
                            <div className="text-xs text-text-secondary">{app.count || 1} emails</div>
                        </div>
                    </div>
                );
            }
        },
        { key: 'role', header: 'Role', sortable: true },
        {
            key: 'status',
            header: 'Status',
            sortable: true,
            render: (app) => (
                <NeoTooltip content={
                    <div>
                        <p className="font-bold text-xs mb-1">AI Reasoning</p>
                        <p className="opacity-90">Matched keywords in email subject.</p>
                        {app.confidence && <p className="mt-1 text-emerald-300">Confidence: {Math.round(app.confidence * 100)}%</p>}
                    </div>
                }>
                    <NeoBadge
                        variant={STATUS_COLORS[app.status]}
                        confidence={app.confidence}
                    >
                        {app.status}
                    </NeoBadge>
                </NeoTooltip>
            )
        },
        {
            key: 'resume',
            header: 'Resume',
            render: (app) => (
                <span className="flex items-center text-text-secondary truncate max-w-[150px]">
                    {app.resume}
                    {(!app.confidence || app.confidence < 0.8) && (
                        <NeoTooltip content="Low confidence mapping">
                            <AlertTriangle className="h-3 w-3 text-amber-500 ml-1" />
                        </NeoTooltip>
                    )}
                </span>
            )
        },
        {
            key: 'updated',
            header: 'Last Update',
            sortable: true,
            render: (app) => (
                <span className="flex items-center text-text-secondary">
                    <Calendar className="h-3 w-3 mr-1" />
                    {app.lastUpdate || 'Just now'}
                </span>
            )
        },
        {
            key: 'actions',
            header: '',
            render: () => (
                <button className="p-1 text-text-muted hover:text-indigo-600 dark:hover:text-indigo-400 rounded-full hover:bg-slate-200 dark:hover:bg-white/10 transition-colors">
                    <MoreHorizontal className="h-4 w-4" />
                </button>
            )
        }
    ];

    return (
        <div className="space-y-6">
            <div className="sm:flex sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-text-primary tracking-tight">Applications</h1>
                    <p className="mt-1 text-sm text-text-secondary">Track and manage your pipeline</p>
                </div>
                <div className="mt-4 sm:mt-0 flex space-x-3">
                    <NeoButton
                        variant="secondary"
                        onClick={() => handleBulkAction('Export')}
                    >
                        <Download className="h-4 w-4 mr-2" /> Export
                    </NeoButton>
                    <NeoButton onClick={() => setShowAddModal(true)}>
                        Add Entry
                    </NeoButton>
                </div>
            </div>

            {/* Filters */}
            <NeoCard className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
                <div className="relative flex-1">
                    <div className="pointer-events-none absolute inset-y-0 left-0 pl-3 flex items-center">
                        <Search className="h-4 w-4 text-text-muted" />
                    </div>
                    <NeoInput
                        ref={searchInputRef}
                        type="text"
                        value={searchQuery}
                        onChange={(e) => handleFilterChange('q', e.target.value)}
                        className="pl-10"
                        placeholder="Search company, role..."
                    />
                </div>
                <div className="flex items-center space-x-2">
                    <NeoSelect
                        className="w-48"
                        value={filterStatus}
                        onChange={(e) => handleFilterChange('status', e.target.value)}
                    >
                        <option value="All">All Statuses</option>
                        <option value="Applied">Applied</option>
                        <option value="Interview R1">Interview</option>
                        <option value="Rejected">Rejected</option>
                    </NeoSelect>
                </div>
            </NeoCard>

            {/* Main Table */}
            <NeoTable
                columns={columns}
                data={filteredApps}
                loading={loading}
                selectable={true}
                selectedIds={selectedIds}
                onSelectionChange={setSelectedIds}
                onRowClick={openDrawer}
                actions={selectedIds.size > 0 && (
                    <div className="flex items-center bg-indigo-50 dark:bg-indigo-900/30 px-3 py-1 rounded-lg border border-indigo-100 dark:border-indigo-800 animate-fadeIn">
                        <span className="text-xs font-bold text-indigo-700 dark:text-indigo-400 mr-2">{selectedIds.size} selected</span>
                        <div className="h-3 w-px bg-indigo-200 dark:bg-indigo-700 mx-2"></div>
                        <button onClick={() => handleBulkAction('Deleted')} className="text-xs text-red-600 dark:text-red-400 font-medium hover:text-red-800 dark:hover:text-red-300 flex items-center">
                            <Trash2 className="h-3 w-3 mr-1" /> Delete
                        </button>
                    </div>
                )}
            />

            <ApplicationDrawer
                application={selectedApp}
                onClose={closeDrawer}
                onUpdate={() => addToast("Changes Saved", "success")}
            />

            <NeoModal
                isOpen={showAddModal}
                onClose={() => setShowAddModal(false)}
                title="Add Application"
            >
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-text-primary mb-1">Company</label>
                        <NeoInput autoFocus placeholder="e.g. Google" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-text-primary mb-1">Role</label>
                        <NeoInput placeholder="e.g. Senior Engineer" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-text-primary mb-1">Initial Status</label>
                        <NeoSelect>
                            <option>Applied</option>
                            <option>Interview</option>
                            <option>Offer</option>
                        </NeoSelect>
                    </div>
                    <div className="flex justify-end pt-4 space-x-3">
                        <NeoButton variant="secondary" onClick={() => setShowAddModal(false)}>
                            Cancel
                        </NeoButton>
                        <NeoButton onClick={handleSave}>
                            Save Entry
                        </NeoButton>
                    </div>
                </div>
            </NeoModal>
        </div>
    );
}
