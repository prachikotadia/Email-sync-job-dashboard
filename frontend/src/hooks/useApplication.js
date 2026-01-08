import { useState, useEffect, useCallback } from 'react';
import { appClient } from '../api/appClient';
import { mockApi } from '../mocks/mockApi';
import { useDemoMode } from './useDemoMode';
import { useToast } from '../context/ToastContext';

export function useApplication(id) {
    const [application, setApplication] = useState(null);
    const [loading, setLoading] = useState(false);
    const { isDemoMode, enableDemoMode } = useDemoMode();
    const { addToast } = useToast();

    const fetchApplication = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        try {
            if (isDemoMode) {
                const data = await mockApi.getApplication(id);
                setApplication(data);
            } else {
                const res = await appClient.get(`/applications/${id}`);
                setApplication(res.data);
            }
        } catch (err) {
            console.error("Failed to fetch application", err);
            if (!isDemoMode) {
                enableDemoMode();
                addToast("Backend unavailable. Switching to Demo Mode.", "warning");
                const data = await mockApi.getApplication(id);
                setApplication(data);
            }
        } finally {
            setLoading(false);
        }
    }, [id, isDemoMode]);

    useEffect(() => {
        fetchApplication();
    }, [fetchApplication]);

    return { application, loading, refresh: fetchApplication };
}
