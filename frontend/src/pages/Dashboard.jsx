import React, { useState, useEffect } from 'react';
import {
    RefreshCcw,
    ArrowUpRight,
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
import { SyncProgress } from './SyncProgress';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';

// Constants would usually be imported
const MOCK_CHART_DATA = [
    { name: 'Applied', value: 45 },
    { name: 'Interview', value: 8 },
    { name: 'Offer', value: 2 },
    { name: 'Rejected', value: 32 },
    { name: 'Ghosted', value: 37 },
];

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
const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#ef4444', '#9ca3af'];

export default function Dashboard() {
    const navigate = useNavigate();
    const { metrics, loading } = useMetrics();
    const [isSyncing, setIsSyncing] = useState(false);
    const [lastSync, setLastSync] = useState(new Date().toLocaleTimeString());
    const [greeting, setGreeting] = useState('Welcome back');
    const [activeIndex, setActiveIndex] = useState(null);

    // Time-based greeting
    useEffect(() => {
        const hour = new Date().getHours();
        if (hour < 12) setGreeting('Good morning');
        else if (hour < 18) setGreeting('Good afternoon');
        else setGreeting('Good evening');
    }, []);

    // Empty State Check
    const metricsList = getMetricsArray(metrics);
    const hasData = metrics && metrics.total > 0;

    const handleSyncComplete = () => {
        setIsSyncing(false);
        setLastSync(new Date().toLocaleTimeString());
    };

    if (!hasData && !loading) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center p-8">
                <NeoCard className="flex flex-col items-center text-center max-w-lg w-full py-12 animate-scaleIn">
                    <div className="bg-indigo-50 dark:bg-indigo-900/30 p-6 rounded-full mb-6 shadow-neo-pressed">
                        <Rocket className="h-10 w-10 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-text-primary mb-2">Welcome to JobPulse AI</h2>
                    <p className="text-text-secondary mb-8">
                        It looks like you haven't synced your emails yet. Connect your Gmail account to automatically track your job applications.
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
            {isSyncing && <SyncProgress onComplete={handleSyncComplete} onClose={() => setIsSyncing(false)} />}

            {/* Header Area in Grid */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 px-1 animate-fadeIn">
                <div>
                    <h1 className="text-3xl font-bold text-text-primary tracking-tight">
                        {greeting}, <span className="text-indigo-600 dark:text-indigo-400">Alex</span>
                    </h1>
                    <p className="text-sm text-text-secondary mt-1">Here's what's happening with your job search today.</p>
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

                {/* Row 2: Status Chart + Needs Review/Action */}
                <div className="col-span-12 lg:col-span-8 animate-slideUp" style={{ animationDelay: '400ms' }}>
                    <NeoCard className="h-[400px] flex flex-col">
                        <div className="flex justify-between items-center mb-6">
                            <div>
                                <h3 className="text-lg font-bold text-text-primary">Application Overview</h3>
                                <p className="text-xs text-text-muted">Current status distribution</p>
                            </div>
                        </div>
                        <div className="flex-1 w-full min-h-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    data={MOCK_CHART_DATA}
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
                                        {MOCK_CHART_DATA.map((entry, index) => (
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
                                                                style={{ backgroundColor: data.payload.fill?.replace('url(#color-', '').replace(')', '') || COLORS[0] }}
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
                                        {MOCK_CHART_DATA.map((entry, index) => (
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
                        </div>
                    </NeoCard>
                </div>

                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6 animate-slideUp" style={{ animationDelay: '500ms' }}>
                    {/* Action Required Widget */}
                    <NeoCard className="flex-1 min-h-[180px] bg-gradient-to-br from-indigo-600 to-indigo-700 text-white relative overflow-hidden !border-none group">
                        <div className="absolute top-0 right-0 -mt-2 -mr-2 bg-white/10 w-32 h-32 rounded-full blur-3xl transition-transform duration-700 group-hover:scale-150"></div>
                        <h3 className="text-lg font-bold relative z-10 mb-2 flex items-center">
                            Action Required
                            <span className="ml-2 flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
                            </span>
                        </h3>
                        <div className="relative z-10 space-y-3">
                            <div className="bg-white/10 backdrop-blur-md p-3 rounded-lg border border-white/10 flex items-center justify-between hover:bg-white/20 transition-colors cursor-pointer">
                                <div>
                                    <p className="font-bold text-sm">Verify 2 Applications</p>
                                    <p className="text-xs text-indigo-200">Low confidence matches</p>
                                </div>
                                <ArrowRight className="h-4 w-4 text-white/70" />
                            </div>
                            <div className="bg-white/10 backdrop-blur-md p-3 rounded-lg border border-white/10 flex items-center justify-between hover:bg-white/20 transition-colors cursor-pointer">
                                <div>
                                    <p className="font-bold text-sm">Upload Resume</p>
                                    <p className="text-xs text-indigo-200">For "Frontend Dev" role</p>
                                </div>
                                <ArrowRight className="h-4 w-4 text-white/70" />
                            </div>
                        </div>
                    </NeoCard>

                    {/* Quick Stat */}
                    <NeoCard className="flex-1 min-h-[150px] flex flex-col justify-center items-center text-center relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-surface dark:to-black/20 pointer-events-none"></div>
                        <p className="text-sm text-text-secondary font-medium relative z-10">Response Rate</p>
                        <p className="text-4xl font-black text-text-primary my-2 relative z-10">12%</p>
                        <p className="text-xs text-emerald-600 dark:text-emerald-400 font-bold bg-emerald-50 dark:bg-emerald-900/20 px-2 py-1 rounded-full relative z-10 flex items-center">
                            <ArrowUpRight className="h-3 w-3 mr-1" />
                            +2% vs last week
                        </p>
                    </NeoCard>
                </div>

                {/* Bottom Row: Recent Activity Timeline */}
                <div className="col-span-12 animate-slideUp" style={{ animationDelay: '600ms' }}>
                    <NeoCard>
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold text-text-primary">Recent Activity</h3>
                            <NeoButton variant="ghost" size="sm" onClick={() => navigate('/applications')}>
                                View All
                            </NeoButton>
                        </div>
                        <div className="relative pl-4 space-y-6 before:absolute before:inset-y-0 before:left-[19px] before:w-0.5 before:bg-slate-200 dark:before:bg-white/10">
                            {[
                                { company: 'Google', status: 'Interview', time: '2h ago', icon: Calendar, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-900/30' },
                                { company: 'Netflix', status: 'Offer Received', time: '5h ago', icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
                                { company: 'Amazon', status: 'Application Sent', time: '1d ago', icon: FileText, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30' }
                            ].map((item, i) => (
                                <div key={i} className="relative pl-8 group">
                                    <div className={cn(
                                        "absolute left-0 top-1 p-1.5 rounded-full border-2 border-white dark:border-app shadow-sm transition-transform group-hover:scale-110",
                                        item.bg, item.color
                                    )}>
                                        <item.icon className="h-3 w-3" />
                                    </div>
                                    <div className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-slate-100 dark:hover:border-white/5">
                                        <div>
                                            <p className="text-sm font-bold text-text-primary">{item.company}</p>
                                            <p className="text-xs text-text-secondary">{item.status}</p>
                                        </div>
                                        <span className="text-xs text-text-muted font-medium flex items-center">
                                            <Clock className="h-3 w-3 mr-1" />
                                            {item.time}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </NeoCard>
                </div>

            </div>
        </div>
    );
}
