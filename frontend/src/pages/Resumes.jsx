import React, { useState } from 'react';
import { Upload, FileText, Trash2, Check, AlertCircle, Sparkles, Edit3, X, Loader2 } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useResumes } from '../hooks/useResumes';
import { cn } from '../utils/cn';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoBadge } from '../ui/NeoBadge';

export default function Resumes() {
    const { addToast } = useToast();
    const { resumes, loading, setResumes } = useResumes();
    const [isDragging, setIsDragging] = useState(false);
    const [pendingMapping, setPendingMapping] = useState([
        { id: 1, company: 'Uber', role: 'Software Engineer', date: '2 days ago', suggested: 'Resume_V4_Final.pdf', confidence: 0.92 },
        { id: 2, company: 'DoorDash', role: 'Frontend Eng', date: '5 days ago', suggested: 'Resume_Frontend_specialized.pdf', confidence: 0.65 },
    ]);

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        // Simulate file add
        addToast("Resume uploaded successfully", "success");
        setResumes(prev => [{ id: Date.now(), name: 'New_Uploaded_Resume.pdf', date: 'Just now', tags: ['New'] }, ...prev]);
    };

    const confirmMapping = (id) => {
        setPendingMapping(prev => prev.filter(m => m.id !== id));
        addToast("Mapping confirmed", "success");
    };

    const handleDeleteResume = (id) => {
        if (window.confirm("Are you sure you want to delete this resume?")) {
            setResumes(prev => prev.filter(r => r.id !== id));
            addToast("Resume deleted", "success");
        }
    };

    const handleEditMapping = (id) => {
        addToast("Edit mode enabled (mock)", "info");
    };

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold text-text-primary tracking-tight">Resumes</h1>
                <p className="mt-1 text-sm text-text-secondary">Manage your resume versions and mapping</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Upload Section */}
                <div className="lg:col-span-2 space-y-6">
                    <div
                        className={cn(
                            "rounded-2xl p-10 flex flex-col items-center justify-center text-center transition-all cursor-pointer border-2 border-dashed",
                            isDragging
                                ? "bg-indigo-50 dark:bg-indigo-900/20 border-indigo-400 shadow-neo-pressed"
                                : "bg-surface border-slate-200 dark:border-white/10 shadow-neo hover:brightness-105"
                        )}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => addToast("This would open file browser", "info")}
                    >
                        <div className="h-14 w-14 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded-2xl shadow-neo-pressed flex items-center justify-center mb-4 transition-transform hover:scale-110">
                            <Upload className="h-7 w-7" />
                        </div>
                        <h3 className="text-lg font-bold text-text-primary">Upload new resume</h3>
                        <p className="mt-1 text-sm text-text-secondary">Drag and drop your PDF here, or click to browse</p>
                        <input type="file" className="hidden" id="file-upload" accept=".pdf" />
                        <p className="mt-2 text-xs text-text-muted">PDF only, max 5MB</p>
                    </div>

                    <NeoCard className="p-0 overflow-hidden">
                        <div className="px-6 py-4 border-b border-white/20 dark:border-white/5 bg-slate-50 dark:bg-white/5">
                            <h3 className="text-lg font-bold text-text-primary">Your Resumes</h3>
                        </div>
                        {loading ? (
                            <div className="p-8 flex justify-center">
                                <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
                            </div>
                        ) : (
                            <ul className="divide-y divide-white/20 dark:divide-white/5">
                                {resumes.map((resume) => (
                                    <li key={resume.id} className="px-6 py-4 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                                        <div className="flex items-center">
                                            <div className="bg-red-50 dark:bg-red-900/20 p-2 rounded-xl mr-4 shadow-neo-pressed text-red-500 dark:text-red-400">
                                                <FileText className="h-6 w-6" />
                                            </div>
                                            <div>
                                                <p className="text-sm font-bold text-text-primary">{resume.name}</p>
                                                <div className="flex items-center mt-1 space-x-2">
                                                    <span className="text-xs text-text-muted">{resume.date}</span>
                                                    {resume.tags?.map(tag => (
                                                        <NeoBadge key={tag} variant="default">
                                                            {tag}
                                                        </NeoBadge>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <button
                                                onClick={() => handleDeleteResume(resume.id)}
                                                className="p-2 text-text-secondary hover:text-red-600 dark:hover:text-red-400 transition-colors rounded-lg hover:shadow-neo-pressed"
                                                title="Delete resume"
                                            >
                                                <Trash2 className="h-5 w-5" />
                                            </button>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </NeoCard>
                </div>

                {/* Map Resumes Helper - Keeping the gradient look but adding neo shadows */}
                <div className="space-y-6">
                    <div className="bg-gradient-to-br from-indigo-900 to-indigo-800 rounded-2xl shadow-neo p-6 text-white relative overflow-hidden">
                        <div className="absolute top-0 right-0 -mt-2 -mr-2 bg-white/10 w-24 h-24 rounded-full blur-2xl"></div>
                        <h3 className="text-lg font-bold mb-4 flex items-center relative z-10">
                            <AlertCircle className="h-5 w-5 text-amber-300 mr-2" />
                            Missing Confirmations
                        </h3>
                        <p className="text-sm text-indigo-100 mb-6 relative z-10">
                            We found {pendingMapping.length} applications where the resume used is unclear or low confidence.
                        </p>

                        <div className="space-y-4 relative z-10">
                            {pendingMapping.map((item) => (
                                <div key={item.id} className="bg-white/10 backdrop-blur-sm rounded-xl p-3 border border-white/10 shadow-lg hover:bg-white/20 transition-colors">
                                    <div className="flex justify-between items-start mb-2">
                                        <div>
                                            <p className="text-sm font-bold text-white">{item.company}</p>
                                            <p className="text-xs text-indigo-200">{item.role}</p>
                                        </div>
                                        <span className="text-xs text-indigo-200">{item.date}</span>
                                    </div>

                                    <div className="mb-3">
                                        <div className="flex items-center text-xs text-indigo-100 mb-1">
                                            <Sparkles className="h-3 w-3 mr-1 text-amber-300" />
                                            AI Suggestion:
                                        </div>
                                        <div className="text-xs bg-black/20 rounded px-2 py-1 truncate">
                                            {item.suggested}
                                            <span className={cn(
                                                "ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded",
                                                item.confidence > 0.8 ? "bg-green-500/20 text-green-300" : "bg-amber-500/20 text-amber-300"
                                            )}>
                                                {item.confidence * 100}%
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex space-x-2">
                                        <button
                                            onClick={() => confirmMapping(item.id)}
                                            className="flex-1 inline-flex justify-center items-center px-3 py-1.5 text-xs font-bold rounded shadow-sm text-indigo-900 bg-white hover:bg-indigo-50 transition-colors"
                                        >
                                            <Check className="h-3 w-3 mr-1" /> Confirm
                                        </button>
                                        <button
                                            onClick={() => handleEditMapping(item.id)}
                                            className="px-2 py-1.5 border border-white/20 rounded hover:bg-white/10 text-white"
                                        >
                                            <Edit3 className="h-3 w-3" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                            {pendingMapping.length === 0 && (
                                <div className="text-center py-6 text-indigo-200 text-sm">
                                    All caught up! 🎉
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
