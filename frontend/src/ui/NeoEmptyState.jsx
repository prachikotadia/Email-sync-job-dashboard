import { cn } from '../utils/cn';
import { LayoutList } from 'lucide-react';

export function NeoEmptyState({ title, description, action, icon: Icon = LayoutList }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="h-24 w-24 bg-surface dark:bg-white/5 rounded-full shadow-neo flex items-center justify-center mb-6 border border-white/20 dark:border-white/5">
                <Icon className="h-10 w-10 text-gray-300 dark:text-gray-600" />
            </div>
            <h3 className="text-lg font-bold text-text-primary">{title}</h3>
            <p className="max-w-sm mt-2 text-text-secondary mb-6">{description}</p>
            {action}
        </div>
    );
}
