import React, { useState, useEffect } from 'react';
import {
    RefreshCcw,
    ArrowRight,
    Rocket,
    Clock,
    CheckCircle
} from 'lucide-react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts';
import { FileText, Briefcase, Calendar, CheckCircle2 } from 'lucide-react';
import { cn } from '../utils/cn';
import { useNavigate } from 'react-router-dom';
import { useMetrics } from '../hooks/useMetrics';
import { useApplications } from '../hooks/useApplications';
import { useAuth } from '../context/AuthContext';
import { SyncProgress } from './SyncProgress';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { formatTimeAgo } from '../utils/format';

// Map metrics object to array for display
const getMetricsArray = (data) => {
    if (!data) return [];
    return [
        { title: 'Total Applications', value: data.total, icon: FileText, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-900/20' },
        { title: 'Active', value: data.active, icon: Briefcase, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/20' },
        { title: 'Interviews', value: data.interviewing, icon: Calendar, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/20' },
        { title: 'Offers', value: data.offers, icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/20' }
    ];
};

// Calculate chart data from real applications
const calculateChartData = (applications) => {
    if (!applications || applications.length === 0) {
        return [];
    }
    
    // Show ALL applications - don't filter by status
    const validApps = applications.filter(app => {
        // Only filter out null/invalid objects
        return app && typeof app === 'object';
    });
    
    const statusCounts = {
        'Applied': 0,
        'Interview': 0,
        'Accepted/Offer': 0,
        'Rejected': 0,
        'Ghosted': 0
    };
    
    validApps.forEach(app => {
        const status = app.status || '';
        if (status.includes('Interview') || status === 'Screening') {
            statusCounts['Interview']++;
        } else if (status === 'Offer' || status === 'Accepted' || status === 'Hired' || status === 'Accepted/Offer') {
            statusCounts['Accepted/Offer']++;
        } else if (status === 'Rejected') {
            statusCounts['Rejected']++;
        } else if (app.ghosted) {
            statusCounts['Ghosted']++;
        } else if (status === 'Applied' || !status) {
            statusCounts['Applied']++;
        }
    });
    
    return Object.entries(statusCounts)
        .filter(([_, count]) => count > 0)
        .map(([name, value]) => ({ name, value }));
};

const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#ef4444', '#9ca3af'];

export default function Dashboard() {
    const navigate = useNavigate();
    const { metrics, loading: metricsLoading } = useMetrics();
    const { applications, loading: applicationsLoading, refresh: refreshApplications } = useApplications();
    const { user } = useAuth();
    const [isSyncing, setIsSyncing] = useState(false);
    const [lastSync, setLastSync] = useState(new Date().toLocaleTimeString());
    const [greeting, setGreeting] = useState('Welcome back');
    const [activeIndex, setActiveIndex] = useState(null);
    const [recentEmails, setRecentEmails] = useState([]);

    // Time-based greeting
    useEffect(() => {
        const hour = new Date().getHours();
        if (hour < 12) setGreeting('Good morning');
        else if (hour < 18) setGreeting('Good afternoon');
        else setGreeting('Good evening');
    }, []);

    // Get user display name (full_name or email or fallback)
    const getUserDisplayName = () => {
        if (user?.full_name) {
            // Use first name if full name has multiple parts, otherwise use full name
            const nameParts = user.full_name.trim().split(/\s+/);
            return nameParts[0] || user.full_name;
        }
        if (user?.email) {
            // Extract name from email (before @) as fallback
            return user.email.split('@')[0];
        }
        return 'there';
    };

    const getUserFullName = () => {
        return user?.full_name || user?.email || 'User';
    };

    // ALWAYS show dashboard - don't hide it even if no data
    const metricsList = getMetricsArray(metrics);
    const hasData = (metrics && metrics.total > 0) || (applications && applications.length > 0);
    const loading = metricsLoading || applicationsLoading;
    
    // Debug logging - CRITICAL for troubleshooting
    useEffect(() => {
        console.log("📊 Dashboard State:", {
            applicationsCount: applications?.length || 0,
            applications: applications,
            metrics: metrics,
            loading: loading,
            hasData: hasData
        });
        if (applications && applications.length > 0) {
            console.log("📊 First 5 applications:", applications.slice(0, 5));
        }
    }, [applications, metrics, loading, hasData]);
    
    // Calculate chart data from real applications
    const chartData = calculateChartData(applications);

    const handleSyncComplete = () => {
        setIsSyncing(false);
        setLastSync(new Date().toLocaleTimeString());
        // Wait for backend to finish storing, then refresh
        setTimeout(() => {
            // Refresh applications multiple times to ensure we get the data
            refreshApplications();
            setTimeout(() => refreshApplications(), 1000);
            setTimeout(() => refreshApplications(), 2000);
            // Dispatch event for Applications page to refresh
            window.dispatchEvent(new CustomEvent('sync-complete'));
            // Force full page reload to show all new emails immediately
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        }, 2000); // Wait 2 seconds for backend to finish processing
    };
    
    const handleEmailAdded = (emailData) => {
        // Add to recent emails list
        setRecentEmails(prev => [...prev, {
            ...emailData,
            id: Date.now() + Math.random(), // Temporary ID
            timestamp: new Date()
        }]);
        // Refresh applications in real-time
        refreshApplications();
    };

    if (!hasData && !loading) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center p-4 md:p-8 relative">
                {/* Show SyncProgress even in empty state */}
                {isSyncing && <SyncProgress onComplete={handleSyncComplete} onClose={() => setIsSyncing(false)} onEmailAdded={handleEmailAdded} />}
                
                <NeoCard className="flex flex-col items-center text-center max-w-lg w-full py-8 md:py-12 px-4 md:px-6 animate-scaleIn">
                    <div className="bg-indigo-50 dark:bg-indigo-900/30 p-6 rounded-full mb-6 shadow-neo-pressed">
                        <Rocket className="h-10 w-10 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-text-primary mb-2">
                        Welcome{user?.full_name ? `, ${getUserDisplayName()}` : ''} to JobPulse AI
                    </h2>
                    <p className="text-text-secondary mb-8">
                        {user?.full_name 
                            ? `${getUserFullName()}, it looks like you haven't synced your emails yet. Connect your Gmail account to automatically track your job applications.`
                            : "It looks like you haven't synced your emails yet. Connect your Gmail account to automatically track your job applications."
                        }
                    </p>
                    <NeoButton
                        onClick={() => setIsSyncing(true)}
                        disabled={isSyncing}
                        className="px-8 py-3 text-lg"
                    >
                        {isSyncing ? 'Syncing...' : 'Sync Emails'} <RefreshCcw className={cn("ml-2 h-5 w-5 inline", isSyncing && "animate-spin")} />
                    </NeoButton>
                </NeoCard>
            </div>
        );
    }

    // Debug: Log applications to console
    useEffect(() => {
        console.log("📊 Dashboard - Applications:", applications);
        console.log("📊 Dashboard - Applications count:", applications?.length);
        console.log("📊 Dashboard - Metrics:", metrics);
        console.log("📊 Dashboard - Loading:", loading);
        console.log("📊 Dashboard - HasData:", hasData);
    }, [applications, metrics, loading, hasData]);

    return (
        <div className="space-y-6 md:space-y-8 relative pb-8">
            {isSyncing && <SyncProgress onComplete={handleSyncComplete} onClose={() => setIsSyncing(false)} onEmailAdded={handleEmailAdded} />}

            {/* Header Area */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 animate-fadeIn">
                <div>
                    <h1 className="text-3xl font-bold text-text-primary tracking-tight">
                        {greeting}, <span className="text-indigo-600 dark:text-indigo-400">{getUserDisplayName()}</span>
                    </h1>
                    <p className="text-sm text-text-secondary mt-1">
                        {user?.full_name 
                            ? `${getUserFullName()}, here's what's happening with your job search today.`
                            : "Here's what's happening with your job search today."
                        }
                    </p>
                </div>
                <div className="flex items-center space-x-4">
                    <div className="text-right hidden sm:block">
                        <p className="text-xs text-text-muted font-bold uppercase tracking-wider">Last synced</p>
                        <p className="text-sm font-semibold text-text-primary">{lastSync}</p>
                    </div>
                    <NeoButton
                        icon={RefreshCcw}
                        variant="secondary"
                        onClick={() => setIsSyncing(true)}
                        className=""
                    >
                        Sync Now
                    </NeoButton>
                </div>
            </div>

            {/* Real-time Email Feed During Sync */}
            {isSyncing && recentEmails.length > 0 && (
                <NeoCard className="animate-slideDown border-2 border-green-200 dark:border-green-800 bg-gradient-to-r from-green-50 to-indigo-50 dark:from-green-900/20 dark:to-indigo-900/20 mb-6">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-500 rounded-lg animate-pulse flex-shrink-0">
                                <CheckCircle className="h-5 w-5 text-white" />
                            </div>
                            <div className="min-w-0">
                                <h3 className="text-lg font-bold text-text-primary truncate">
                                    Adding Emails Step by Step
                                </h3>
                                <p className="text-sm text-text-secondary">
                                    {recentEmails.length} email{recentEmails.length !== 1 ? 's' : ''} processed and stored
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {recentEmails.slice().reverse().map((email, i) => (
                            <div 
                                key={email.id || i} 
                                className="bg-white dark:bg-slate-800 rounded-lg p-3 border-2 border-green-300 dark:border-green-700 shadow-lg animate-scaleIn hover:scale-105 transition-transform overflow-hidden"
                                style={{ animationDelay: `${i * 50}ms` }}
                            >
                                <div className="flex items-start gap-2">
                                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse flex-shrink-0 mt-1.5"></div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-bold text-text-primary truncate mb-1">
                                            {email.company_name || 'New Application'}
                                        </p>
                                        <p className="text-xs text-text-secondary truncate mb-2">
                                            {email.role || 'Job Application'}
                                        </p>
                                        <span className="inline-block px-2 py-0.5 text-xs font-semibold rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                                            {email.status || 'Applied'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </NeoCard>
            )}

            {/* 12-Column Grid Layout */}
            <div className="grid grid-cols-12 gap-4 md:gap-6">

                {/* Row 1: KPI Cards - Staggered Animation */}
                {metricsList.map((stat, index) => (
                    <div
                        key={index}
                        className="col-span-12 sm:col-span-6 lg:col-span-3 animate-slideUp mb-4 md:mb-0"
                        style={{ animationDelay: `${index * 100}ms` }}
                    >
                        <NeoCard className="flex items-center space-x-3 md:space-x-4 h-full hover:shadow-lg hover:-translate-y-1 transition-all duration-300 cursor-default group p-4 md:p-6">
                            <div className={cn("p-3 md:p-4 rounded-xl flex-shrink-0 shadow-neo-pressed transition-transform group-hover:scale-110 duration-300", stat.bg)}>
                                <stat.icon className={cn("h-5 w-5 md:h-6 md:w-6", stat.color)} />
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-xs font-bold text-text-secondary uppercase tracking-wide truncate">{stat.title}</p>
                                <p className="text-xl md:text-2xl font-bold text-text-primary mt-1">
                                    {loading ? "..." : (stat.value ?? 0)}
                                    {stat.title === 'Total Applications' && metrics?.total_emails && metrics.total_emails > (stat.value ?? 0) && (
                                        <span className="ml-2 text-sm font-normal text-text-secondary">
                                            ({metrics.total_emails} emails)
                                        </span>
                                    )}
                                </p>
                            </div>
                        </NeoCard>
                    </div>
                ))}

                {/* Row 2: Status Chart and Profile - Clear Row Separation */}
                <div className="col-span-12 lg:col-span-8 animate-slideUp mb-4 md:mb-0" style={{ animationDelay: '400ms' }}>
                    <NeoCard className="flex flex-col p-4 md:p-6 w-full">
                        <div className="flex justify-between items-center mb-4 md:mb-6">
                            <div>
                                <h3 className="text-base md:text-lg font-bold text-text-primary">Application Overview</h3>
                                <p className="text-xs text-text-muted mt-0.5">Current status distribution</p>
                            </div>
                        </div>
                        <div className="w-full overflow-hidden" style={{ height: '280px', minHeight: '280px' }}>
                            {chartData.length === 0 ? (
                                <div className="flex items-center justify-center h-full text-text-secondary">
                                    <p>No data available</p>
                                </div>
                            ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    data={chartData}
                                    margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                                    onMouseMove={(state) => {
                                        if (state.isTooltipActive) {
                                            setActiveIndex(state.activeTooltipIndex);
                                        } else {
                                            setActiveIndex(null);
                                        }
                                    }}
                                    onMouseLeave={() => setActiveIndex(null)}
                                >
                                    <defs>
                                        {chartData.map((entry, index) => (
                                            <linearGradient key={`gradient-${index}`} id={`color-${index}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={COLORS[index % COLORS.length]} stopOpacity={0.8} />
                                                <stop offset="95%" stopColor={COLORS[index % COLORS.length]} stopOpacity={0.3} />
                                            </linearGradient>
                                        ))}
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--text-muted)" strokeOpacity={0.1} />
                                    <XAxis
                                        dataKey="name"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 13, fontWeight: 500 }}
                                        axisLine={false}
                                        tickLine={false}
                                        dy={15}
                                    />
                                    <YAxis
                                        tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                        axisLine={false}
                                        tickLine={false}
                                        dx={-10}
                                    />
                                    <Tooltip
                                        cursor={{ fill: 'var(--bg-surface)', opacity: 0.5, radius: [8, 8, 0, 0] }}
                                        contentStyle={{ 
                                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                            border: '1px solid rgba(0, 0, 0, 0.1)',
                                            borderRadius: '12px',
                                            padding: '12px',
                                            zIndex: 1000
                                        }}
                                        content={({ active, payload, label }) => {
                                            if (active && payload && payload.length) {
                                                const data = payload[0];
                                                return (
                                                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-md border border-slate-200 dark:border-slate-700 p-3 rounded-xl shadow-lg z-[1000]">
                                                        <p className="text-sm font-bold text-text-secondary mb-1">{label}</p>
                                                        <div className="flex items-center space-x-2">
                                                            <div
                                                                className="w-3 h-3 rounded-full flex-shrink-0"
                                                                style={{ backgroundColor: COLORS[chartData.findIndex(d => d.name === label) % COLORS.length] }}
                                                            />
                                                            <p className="text-lg font-bold text-text-primary">
                                                                {data.value}
                                                                <span className="text-xs font-normal text-text-muted ml-1">apps</span>
                                                            </p>
                                                        </div>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                    <Bar
                                        dataKey="value"
                                        radius={[8, 8, 8, 8]}
                                        barSize={40}
                                        animationDuration={1500}
                                    >
                                        {chartData.map((entry, index) => (
                                            <Cell
                                                key={`cell-${index}`}
                                                fill={`url(#color-${index})`}
                                                stroke={COLORS[index % COLORS.length]}
                                                strokeWidth={activeIndex === index ? 3 : 0}
                                                style={{
                                                    transition: 'all 0.3s ease',
                                                    filter: activeIndex !== null && activeIndex !== index ? 'opacity(0.6)' : 'opacity(1)'
                                                }}
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                            )}
                        </div>
                    </NeoCard>
                </div>

                <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 md:gap-6 animate-slideUp mb-4 md:mb-0" style={{ animationDelay: '500ms' }}>
                    {/* User Profile Widget */}
                    {user && (
                        <NeoCard className="p-4 md:p-6 bg-gradient-to-br from-indigo-50 to-indigo-100 dark:from-indigo-900/20 dark:to-indigo-800/20 border-indigo-200 dark:border-indigo-800/50 w-full">
                            <div className="flex items-center space-x-3 md:space-x-4">
                                <div className="h-12 w-12 md:h-14 md:w-14 rounded-xl bg-indigo-600 dark:bg-indigo-500 flex items-center justify-center text-white font-bold text-lg md:text-xl shadow-neo-button flex-shrink-0">
                                    {(user.full_name || user.email)?.charAt(0).toUpperCase() || 'U'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-bold text-indigo-900 dark:text-indigo-200 truncate">
                                        {user.full_name || 'User'}
                                    </p>
                                    <p className="text-xs text-indigo-700 dark:text-indigo-300 truncate mt-0.5">
                                        {user.email}
                                    </p>
                                    <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-1">
                                        {user.role === 'editor' ? '👑 Editor' : '👁️ Viewer'}
                                    </p>
                                </div>
                            </div>
                        </NeoCard>
                    )}
                </div>

                {/* Bottom Row: Recent Activity Timeline */}
                <div className="col-span-12 animate-slideUp mt-4 md:mt-0" style={{ animationDelay: '600ms' }}>
                    <NeoCard className="p-4 md:p-6 w-full">
                        <div className="flex items-center justify-between mb-4 md:mb-6 flex-wrap gap-2">
                            <h3 className="text-base md:text-lg font-bold text-text-primary">
                                Recent Activity
                                {isSyncing && recentEmails.length > 0 && (
                                    <span className="ml-2 text-xs md:text-sm font-normal text-indigo-600 dark:text-indigo-400 animate-pulse">
                                        • Adding {recentEmails.length} email{recentEmails.length !== 1 ? 's' : ''}...
                                    </span>
                                )}
                            </h3>
                            <NeoButton variant="ghost" size="sm" onClick={() => navigate('/applications')} className="flex-shrink-0">
                                View All
                            </NeoButton>
                        </div>
                        <div className="relative pl-4 md:pl-6 space-y-3 md:space-y-4 max-h-[600px] overflow-y-auto overflow-x-hidden pr-2 md:pr-4">
                            {/* Timeline line - positioned to not overlap */}
                            <div className="absolute left-[15px] md:left-[23px] top-0 bottom-0 w-0.5 bg-slate-200 dark:bg-white/10 z-0"></div>
                            {/* Show recently added emails first during sync */}
                            {isSyncing && recentEmails.length > 0 && (
                                <>
                                    {recentEmails.slice().reverse().map((email, i) => (
                                        <div key={email.id || i} className="relative pl-8 md:pl-10 group animate-slideInRight z-10" style={{ animationDelay: `${i * 50}ms` }}>
                                            <div className="absolute left-0 top-1.5 p-1.5 md:p-2 rounded-full border-2 border-white dark:border-app shadow-md bg-green-100 dark:bg-green-900/30 text-green-500 animate-pulse z-20">
                                                <CheckCircle className="h-2.5 w-2.5 md:h-3 md:w-3" />
                                            </div>
                                            <div className="flex items-center justify-between p-2.5 md:p-3 rounded-xl bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 hover:bg-green-100 dark:hover:bg-green-900/20 transition-all gap-2 ml-1">
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs md:text-sm font-bold text-text-primary truncate">
                                                        {email.company_name || 'New Application'}
                                                        <span className="ml-2 text-xs font-normal text-green-600 dark:text-green-400">NEW</span>
                                                    </p>
                                                    <p className="text-xs text-text-secondary truncate mt-0.5">{email.role || 'Job Application'}</p>
                                                    <p className="text-xs text-green-600 dark:text-green-400 mt-1">{email.status || 'Applied'}</p>
                                                </div>
                                                <span className="text-xs text-text-muted font-medium flex items-center flex-shrink-0">
                                                    <Clock className="h-3 w-3 mr-1" />
                                                    Just now
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </>
                            )}
                            {/* ALWAYS SHOW ALL APPLICATIONS - NO FILTERING */}
                            {loading ? (
                                <div className="text-center py-8 text-text-secondary">
                                    <p>Loading applications...</p>
                                </div>
                            ) : applications && applications.length > 0 ? (
                                // Show ALL applications - sorted by most recent first - NO LIMIT
                                applications
                                    .sort((a, b) => {
                                        // Sort by last_email_date or created_at, most recent first
                                        const dateA = new Date(a.last_email_date || a.created_at || a.updated_at || 0);
                                        const dateB = new Date(b.last_email_date || b.created_at || b.updated_at || 0);
                                        return dateB - dateA;
                                    })
                                    // REMOVED .slice(0, 10) - SHOW ALL APPLICATIONS
                                    .map((app, i) => {
                                    // Determine icon and color based on status
                                    let icon = FileText;
                                    let color = 'text-blue-500';
                                    let bg = 'bg-blue-100 dark:bg-blue-900/30';
                                    
                                    if (app.status && (app.status.includes('Interview') || app.status === 'Screening')) {
                                        icon = Calendar;
                                        color = 'text-amber-500';
                                        bg = 'bg-amber-100 dark:bg-amber-900/30';
                                    } else if (app.status === 'Rejected') {
                                        icon = FileText;
                                        color = 'text-red-500';
                                        bg = 'bg-red-100 dark:bg-red-900/30';
                                    } else if (app.status === 'Offer' || app.status === 'Accepted' || app.status === 'Hired' || app.status === 'Accepted/Offer') {
                                        icon = CheckCircle;
                                        color = 'text-emerald-500';
                                        bg = 'bg-emerald-100 dark:bg-emerald-900/30';
                                    }
                                    
                                    // Format time ago
                                    const timeAgo = app.last_email_date 
                                        ? formatTimeAgo(app.last_email_date)
                                        : 'Unknown';
                                    
                                    return (
                                        <div key={app.id || i} className="relative pl-8 md:pl-10 group z-10">
                                            <div className={cn(
                                                "absolute left-0 top-1.5 p-1.5 md:p-2 rounded-full border-2 border-white dark:border-app shadow-md transition-transform group-hover:scale-110 z-20",
                                                bg, color
                                            )}>
                                                {React.createElement(icon, { className: "h-2.5 w-2.5 md:h-3 md:w-3" })}
                                            </div>
                                            <div className="flex items-center justify-between p-2.5 md:p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-slate-100 dark:hover:border-white/5 gap-2 ml-1">
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs md:text-sm font-bold text-text-primary truncate">{app.company_name}</p>
                                                    <p className="text-xs text-text-secondary truncate mt-0.5">{app.status || 'Applied'}</p>
                                                </div>
                                                <span className="text-xs text-text-muted font-medium flex items-center flex-shrink-0">
                                                    <Clock className="h-3 w-3 mr-1" />
                                                    {timeAgo}
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="text-center py-8 text-text-secondary">
                                    <p>No recent activity</p>
                                </div>
                            )}
                        </div>
                    </NeoCard>
                </div>

            </div>
        </div>
    );
}
