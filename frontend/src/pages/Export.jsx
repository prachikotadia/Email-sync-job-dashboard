import React, { useState } from 'react';
import { Download, Calendar, Filter, FileSpreadsheet } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoSelect } from '../ui/NeoInput';
import { apiClient } from '../services/api';
import { useDemoMode } from '../hooks/useDemoMode';

export default function Export() {
    const { addToast } = useToast();
    const { isDemoMode } = useDemoMode();
    const [dateRange, setDateRange] = useState('30');
    const [statusFilter, setStatusFilter] = useState('all');
    const [isExporting, setIsExporting] = useState(false);

    const handleExport = async () => {
        setIsExporting(true);
        addToast("Generating export...", "info");

        try {
            if (isDemoMode) {
                // Demo mode - simulate export
                setTimeout(() => {
                    setIsExporting(false);
                    addToast("Export downloaded successfully (Demo Mode)", "success");
                }, 2000);
                return;
            }

            // Real API call to export endpoint
            const response = await apiClient.get('/export/excel', {
                responseType: 'blob', // Important for file downloads
            });

            // Create download link
            const blob = new Blob([response.data], {
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            
            // Extract filename from Content-Disposition header if available
            const contentDisposition = response.headers['content-disposition'];
            let filename = 'applications_export.xlsx';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            setIsExporting(false);
            addToast("Export downloaded successfully", "success");
        } catch (error) {
            console.error('Export error:', error);
            setIsExporting(false);
            const message = error.response?.data?.error?.message || error.message || 'Failed to export data';
            addToast(message, "error");
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-8">
            <div>
                <h1 className="text-3xl font-bold text-text-primary tracking-tight">Export Data</h1>
                <p className="mt-1 text-sm text-text-secondary">Download your application history for analysis</p>
            </div>

            <NeoCard className="p-8">
                <div className="flex items-center justify-center mb-8">
                    <div className="h-20 w-20 bg-green-50 dark:bg-green-900/30 rounded-2xl shadow-neo-pressed flex items-center justify-center text-green-600 dark:text-green-400">
                        <FileSpreadsheet className="h-10 w-10" />
                    </div>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-text-primary mb-2">
                            <Calendar className="inline-block h-4 w-4 mr-1 text-text-muted" />
                            Date Range
                        </label>
                        <NeoSelect
                            value={dateRange}
                            onChange={(e) => setDateRange(e.target.value)}
                        >
                            <option value="7">Last 7 days</option>
                            <option value="30">Last 30 days</option>
                            <option value="90">Last 3 months</option>
                            <option value="all">All time</option>
                        </NeoSelect>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-text-primary mb-2">
                            <Filter className="inline-block h-4 w-4 mr-1 text-text-muted" />
                            Status Filter
                        </label>
                        <NeoSelect
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                        >
                            <option value="all">All Statuses</option>
                            <option value="active">Active (Applied, Interview, Offer)</option>
                            <option value="closed">Closed (Rejected, Ghosted)</option>
                        </NeoSelect>
                    </div>

                    <div className="pt-4">
                        <NeoButton
                            onClick={handleExport}
                            disabled={isExporting}
                            className="w-full flex justify-center items-center py-3 text-lg disabled:opacity-75 disabled:cursor-not-allowed"
                        >
                            {isExporting ? 'Generating...' : (
                                <>
                                    <Download className="mr-2 h-5 w-5" />
                                    Download Excel Report
                                </>
                            )}
                        </NeoButton>
                        <p className="mt-3 text-center text-xs text-text-muted">
                            Includes metadata, email counts, and timeline events.
                        </p>
                    </div>
                </div>
            </NeoCard>
        </div>
    );
}
