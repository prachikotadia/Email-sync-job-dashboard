import React, { useState } from 'react';
import { ChevronRight, ChevronLeft, ArrowUpDown, Filter, EyeOff, LayoutList, AlignJustify } from 'lucide-react';
import { NeoCard } from './NeoCard';
import { NeoButton } from './NeoButton';
import { NeoSkeleton } from './NeoSkeleton';
import { NeoEmptyState } from './NeoEmptyState';
import { cn } from '../utils/cn';

export function NeoTable({
    columns,
    data,
    loading,
    onRowClick,
    keyField = 'id',
    selectable = false,
    selectedIds = new Set(),
    onSelectionChange,
    actions
}) {
    const [density, setDensity] = useState('comfortable'); // 'compact' | 'comfortable'
    const [hiddenColumns, setHiddenColumns] = useState(new Set());
    // Pagination state could be lifted or internal
    const [page, setPage] = useState(1);

    const toggleColumn = (key) => {
        const newHidden = new Set(hiddenColumns);
        if (newHidden.has(key)) newHidden.delete(key);
        else newHidden.add(key);
        setHiddenColumns(newHidden);
    };

    const isAllSelected = data.length > 0 && selectedIds.size === data.length;

    const handleSelectAll = (e) => {
        e.stopPropagation();
        if (!onSelectionChange) return;
        if (isAllSelected) {
            onSelectionChange(new Set());
        } else {
            onSelectionChange(new Set(data.map(d => d[keyField])));
        }
    };

    const handleSelectRow = (id, e) => {
        e.stopPropagation();
        if (!onSelectionChange) return;
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) newSet.delete(id);
        else newSet.add(id);
        onSelectionChange(newSet);
    };

    const visibleColumns = columns.filter(c => !hiddenColumns.has(c.key));

    return (
        <NeoCard className="p-0 overflow-hidden flex flex-col min-h-[500px]">
            {/* Toolbar */}
            <div className="px-6 py-4 bg-surface border-b border-gray-200/50 dark:border-white/5 flex flex-col sm:flex-row justify-between items-center space-y-3 sm:space-y-0">
                <div className="flex items-center space-x-2">
                    {actions}
                </div>
                <div className="flex items-center space-x-3">
                    {/* Density Toggle */}
                    <div className="flex items-center bg-app dark:bg-white/5 rounded-lg p-1">
                        <button
                            onClick={() => setDensity('compact')}
                            className={cn(
                                "p-1.5 rounded transition-all",
                                density === 'compact' ? "bg-surface shadow-sm text-indigo-600 dark:text-indigo-400" : "text-text-secondary hover:text-text-primary"
                            )}
                            title="Compact view"
                        >
                            <AlignJustify className="h-4 w-4" />
                        </button>
                        <button
                            onClick={() => setDensity('comfortable')}
                            className={cn(
                                "p-1.5 rounded transition-all",
                                density === 'comfortable' ? "bg-surface shadow-sm text-indigo-600 dark:text-indigo-400" : "text-text-secondary hover:text-text-primary"
                            )}
                            title="Comfortable view"
                        >
                            <LayoutList className="h-4 w-4" />
                        </button>
                    </div>

                    {/* Column Visibility */}
                    <div className="relative group">
                        <NeoButton variant="secondary" size="sm" className="px-2">
                            <EyeOff className="h-4 w-4" />
                        </NeoButton>
                        <div className="absolute right-0 mt-2 w-48 bg-surface rounded-xl shadow-xl z-50 hidden group-hover:block p-2 border border-white/10 animate-fadeIn">
                            <p className="text-xs font-bold text-text-muted px-2 py-1 uppercase">Toggle Columns</p>
                            {columns.slice(1).map(col => (
                                <label key={col.key} className="flex items-center px-2 py-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 mr-2"
                                        checked={!hiddenColumns.has(col.key)}
                                        onChange={() => toggleColumn(col.key)}
                                    />
                                    <span className="text-sm text-text-primary">{col.header}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Table Content */}
            <div className="flex-1 overflow-x-auto custom-scrollbar bg-app/50 dark:bg-black/20">
                {loading ? <NeoSkeleton density={density} /> : data.length === 0 ? (
                    <NeoEmptyState
                        title="No records found"
                        description="Try adjusting your filters or search query to find what you're looking for."
                    />
                ) : (
                    <table className="min-w-full divide-y divide-gray-200/50 dark:divide-white/5">
                        <thead className="bg-surface">
                            <tr>
                                {selectable && (
                                    <th scope="col" className="px-6 py-3 text-left w-12">
                                        <input
                                            type="checkbox"
                                            className="rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 bg-transparent"
                                            checked={isAllSelected}
                                            onChange={handleSelectAll}
                                        />
                                    </th>
                                )}
                                {visibleColumns.map((col, idx) => (
                                    <th
                                        key={col.key}
                                        scope="col"
                                        className={cn(
                                            "px-6 py-3 text-left text-xs font-bold text-text-secondary uppercase tracking-wider",
                                            idx === 0 && "sticky left-0 bg-surface z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)]"
                                        )}
                                    >
                                        <div className="flex items-center space-x-1 cursor-pointer hover:text-text-primary">
                                            <span>{col.header}</span>
                                            {col.sortable && <ArrowUpDown className="h-3 w-3" />}
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="bg-transparent divide-y divide-gray-200/50 dark:divide-white/5">
                            {data.map((row) => (
                                <tr
                                    key={row[keyField]}
                                    className={cn(
                                        "transition-all cursor-pointer group hover:bg-surface hover:shadow-sm",
                                        selectedIds.has(row[keyField]) && "bg-indigo-50/40 dark:bg-indigo-900/20"
                                    )}
                                    onClick={() => onRowClick && onRowClick(row)}
                                >
                                    {selectable && (
                                        <td className={cn("px-6 whitespace-nowrap", density === 'compact' ? 'py-2' : 'py-4')} onClick={(e) => e.stopPropagation()}>
                                            <input
                                                type="checkbox"
                                                className="rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 bg-transparent"
                                                checked={selectedIds.has(row[keyField])}
                                                onChange={(e) => handleSelectRow(row[keyField], e)}
                                            />
                                        </td>
                                    )}
                                    {visibleColumns.map((col, idx) => (
                                        <td
                                            key={col.key}
                                            className={cn(
                                                "px-6 whitespace-nowrap text-sm text-text-primary",
                                                density === 'compact' ? 'py-2' : 'py-4',
                                                idx === 0 && "sticky left-0 bg-app dark:bg-slate-900 group-hover:bg-surface z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] font-medium"
                                            )}
                                        >
                                            {col.render ? col.render(row) : row[col.key]}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination (Simple - Visual Only as per mock) */}
            <div className="bg-surface px-6 py-3 border-t border-gray-200/50 dark:border-white/5 flex items-center justify-between">
                <div className="text-xs text-text-secondary">
                    Showing <span className="font-medium text-text-primary">1</span> to <span className="font-medium text-text-primary">{Math.min(data.length, 10)}</span> of <span className="font-medium text-text-primary">{data.length}</span> results
                </div>
                <div className="flex space-x-2">
                    <NeoButton variant="secondary" size="sm" disabled className="px-2">
                        <ChevronLeft className="h-4 w-4" />
                    </NeoButton>
                    <NeoButton variant="secondary" size="sm" disabled className="px-2">
                        <ChevronRight className="h-4 w-4" />
                    </NeoButton>
                </div>
            </div>
        </NeoCard>
    );
}
