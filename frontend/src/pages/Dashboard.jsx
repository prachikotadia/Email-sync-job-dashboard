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
    
    // Filter out invalid statuses first
    const validStatuses = ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer", 
                           "Screening", "Interview (R1)", "Interview (R2)", "Interview (Final)",
                           "Offer", "Accepted", "Hired"];
    const validApps = applications.filter(app => {
        const status = app.status || "";
        const isValid = validStatuses.includes(status) || 
                       status.includes("Interview") || 
                       ["Offer", "Accepted", "Hired"].includes(status);
        return isValid && status !== "Unknown";
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

    // Empty State Check
    const metricsList = getMetricsArray(metrics);
    const hasData = metrics && metrics.total > 0;
    const loading = metricsLoading || applicationsLoading;
    
    // Calculate chart data from real applications
    const chartData = calculateChartData(applications);

    const handleSyncComplete = () => {
        setIsSyncing(false);
        setLastSync(new Date().toLocaleTimeString());
        // Refresh applications after sync
        refreshApplications();
        // Clear recent emails after a delay
        setTimeout(() => setRecentEmails([]), 5000);
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
            <div className="min-h-[60vh] flex flex-col items-center justify-center p-8">
                <NeoCard className="flex flex-col items-center text-center max-w-lg w-full py-12 animate-scaleIn">
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
                        onClick={() => navigate('/onboarding')}
                        className="px-8 py-3 text-lg"
                    >
                        Get Started <ArrowRight className="ml-2 h-5 w-5 inline" />
                    </NeoButton>
                </NeoCard>
            </div>
        );
    }

    return (
        <div className="space-y-8 relative">
            {isSyncing && <SyncProgress onComplete={handleSyncComplete} onClose={() => setIsSyncing(false)} onEmailAdded={handleEmailAdded} />}

            {/* Header Area in Grid */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 px-1 animate-fadeIn">
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
                <NeoCard className="mb-6 animate-slideDown border-2 border-green-200 dark:border-green-800 bg-gradient-to-r from-green-50 to-indigo-50 dark:from-green-900/20 dark:to-indigo-900/20">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-500 rounded-lg animate-pulse">
                                <CheckCircle className="h-5 w-5 text-white" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-text-primary">
                                    Adding Emails Step by Step
                                </h3>
                                <p className="text-sm text-text-secondary">
                                    {recentEmails.length} email{recentEmails.length !== 1 ? 's' : ''} processed and stored
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {recentEmails.slice().reverse().map((email, i) => (
                            <div 
                                key={email.id || i} 
                                className="bg-white dark:bg-slate-800 rounded-lg p-4 border-2 border-green-300 dark:border-green-700 shadow-lg animate-scaleIn hover:scale-105 transition-transform"
                                style={{ animationDelay: `${i * 100}ms` }}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                                            <p className="text-sm font-bold text-text-primary truncate">
                                                {email.company_name || 'New Application'}
                                            </p>
                                        </div>
                                        <p className="text-xs text-text-secondary truncate mb-1">
                                            {email.role || 'Job Application'}
                                        </p>
                                        <span className="inline-block px-2 py-1 text-xs font-semibold rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
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
            <div className="grid grid-cols-12 gap-6">

                {/* Row 1: KPI Cards - Staggered Animation */}
                {metricsList.map((stat, index) => (
                    <div
                        key={index}
                        className="col-span-12 sm:col-span-6 lg:col-span-3 animate-slideUp"
                        style={{ animationDelay: `${index * 100}ms` }}
                    >
                        <NeoCard className="flex items-center space-x-4 h-full hover:shadow-lg hover:-translate-y-1 transition-all duration-300 cursor-default group">
                            <div className={cn("p-4 rounded-xl flex-shrink-0 shadow-neo-pressed transition-transform group-hover:scale-110 duration-300", stat.bg)}>
                                <stat.icon className={cn("h-6 w-6", stat.color)} />
                            </div>
                            <div>
                                <p className="text-xs font-bold text-text-secondary uppercase tracking-wide">{stat.title}</p>
                                <p className="text-2xl font-bold text-text-primary mt-1">
                                    {loading ? "..." : stat.value}
                                </p>
                            </div>
                        </NeoCard>
                    </div>
                ))}

                {/* Row 2: Status Chart */}
                <div className="col-span-12 lg:col-span-8 animate-slideUp" style={{ animationDelay: '400ms' }}>
                    <NeoCard className="h-[400px] flex flex-col">
                        <div className="flex justify-between items-center mb-6">
                            <div>
                                <h3 className="text-lg font-bold text-text-primary">Application Overview</h3>
                                <p className="text-xs text-text-muted">Current status distribution</p>
                            </div>
                        </div>
                        <div className="flex-1 w-full" style={{ height: '340px', minHeight: '300px', width: '100%', position: 'relative' }}>
                            {chartData.length === 0 ? (
                                <div className="flex items-center justify-center h-full text-text-secondary">
                                    <p>No data available</p>
                                </div>
                            ) : (
                            <ResponsiveContainer width="100%" height={340}>
                                <BarChart
                                    data={chartData}
                                    margin={{ top: 20, right: 30, left: 0, bottom: 0 }}
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
                                        content={({ active, payload, label }) => {
                                            if (active && payload && payload.length) {
                                                const data = payload[0];
                                                return (
                                                    <div className="bg-white/90 dark:bg-black/80 backdrop-blur-md border border-white/50 dark:border-white/10 p-4 rounded-2xl shadow-neo-button">
                                                        <p className="text-sm font-bold text-text-secondary mb-1">{label}</p>
                                                        <div className="flex items-center space-x-2">
                                                            <div
                                                                className="w-3 h-3 rounded-full"
                                                                style={{ backgroundColor: COLORS[chartData.findIndex(d => d.name === label) % COLORS.length] }}
                                                            />
                                                            <p className="text-xl font-bold text-text-primary">
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
                                        barSize={45}
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

                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6 animate-slideUp" style={{ animationDelay: '500ms' }}>
                    {/* User Profile Widget */}
                    {user && (
                        <NeoCard className="p-6 bg-gradient-to-br from-indigo-50 to-indigo-100 dark:from-indigo-900/20 dark:to-indigo-800/20 border-indigo-200 dark:border-indigo-800/50">
                            <div className="flex items-center space-x-4">
                                <div className="h-14 w-14 rounded-xl bg-indigo-600 dark:bg-indigo-500 flex items-center justify-center text-white font-bold text-xl shadow-neo-button flex-shrink-0">
                                    {(user.full_name || user.email)?.charAt(0).toUpperCase() || 'U'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-bold text-indigo-900 dark:text-indigo-200 truncate">
                                        {user.full_name || 'User'}
                                    </p>
                                    <p className="text-xs text-indigo-700 dark:text-indigo-300 truncate">
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
                <div className="col-span-12 animate-slideUp" style={{ animationDelay: '600ms' }}>
                    <NeoCard>
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold text-text-primary">
                                Recent Activity
                                {isSyncing && recentEmails.length > 0 && (
                                    <span className="ml-2 text-sm font-normal text-indigo-600 dark:text-indigo-400 animate-pulse">
                                        • Adding {recentEmails.length} email{recentEmails.length !== 1 ? 's' : ''}...
                                    </span>
                                )}
                            </h3>
                            <NeoButton variant="ghost" size="sm" onClick={() => navigate('/applications')}>
                                View All
                            </NeoButton>
                        </div>
                        <div className="relative pl-4 space-y-6 before:absolute before:inset-y-0 before:left-[19px] before:w-0.5 before:bg-slate-200 dark:before:bg-white/10">
                            {/* Show recently added emails first during sync */}
                            {isSyncing && recentEmails.length > 0 && (
                                <>
                                    {recentEmails.slice().reverse().map((email, i) => (
                                        <div key={email.id || i} className="relative pl-8 group animate-slideInRight" style={{ animationDelay: `${i * 100}ms` }}>
                                            <div className="absolute left-0 top-1 p-1.5 rounded-full border-2 border-white dark:border-app shadow-sm bg-green-100 dark:bg-green-900/30 text-green-500 animate-pulse">
                                                <CheckCircle className="h-3 w-3" />
                                            </div>
                                            <div className="flex items-center justify-between p-3 rounded-xl bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 hover:bg-green-100 dark:hover:bg-green-900/20 transition-all">
                                                <div>
                                                    <p className="text-sm font-bold text-text-primary">
                                                        {email.company_name || 'New Application'}
                                                        <span className="ml-2 text-xs font-normal text-green-600 dark:text-green-400">NEW</span>
                                                    </p>
                                                    <p className="text-xs text-text-secondary">{email.role || 'Job Application'}</p>
                                                    <p className="text-xs text-green-600 dark:text-green-400 mt-1">{email.status || 'Applied'}</p>
                                                </div>
                                                <span className="text-xs text-text-muted font-medium flex items-center">
                                                    <Clock className="h-3 w-3 mr-1" />
                                                    Just now
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </>
                            )}
                            {applications && applications.length > 0 ? (
                                // Filter out invalid statuses before displaying
                                applications
                                    .filter(app => {
                                        const status = app.status || "";
                                        const validStatuses = ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer", 
                                                             "Screening", "Interview (R1)", "Interview (R2)", "Interview (Final)",
                                                             "Offer", "Accepted", "Hired"];
                                        const isValid = validStatuses.includes(status) || 
                                                       status.includes("Interview") || 
                                                       ["Offer", "Accepted", "Hired"].includes(status);
                                        return isValid && status !== "Unknown";
                                    })
                                    .slice(0, 5)
                                    .map((app, i) => {
                                    // Determine icon and color based on status
                                    let icon = FileText;
                                    let color = 'text-blue-500';
                                    let bg = 'bg-blue-100 dark:bg-blue-900/30';
                                    
                                    if (app.status && (app.status.includes('Interview') || app.status === 'Screening')) {
                                        icon = Calendar;
                                        color = 'text-amber-500';
                                        bg = 'bg-amber-100 dark:bg-amber-900/30';
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
                                        <div key={app.id || i} className="relative pl-8 group">
                                            <div className={cn(
                                                "absolute left-0 top-1 p-1.5 rounded-full border-2 border-white dark:border-app shadow-sm transition-transform group-hover:scale-110",
                                                bg, color
                                            )}>
                                                {React.createElement(icon, { className: "h-3 w-3" })}
                                            </div>
                                            <div className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-slate-100 dark:hover:border-white/5">
                                                <div>
                                                    <p className="text-sm font-bold text-text-primary">{app.company_name}</p>
                                                    <p className="text-xs text-text-secondary">{app.status || 'Applied'}</p>
                                                </div>
                                                <span className="text-xs text-text-muted font-medium flex items-center">
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
