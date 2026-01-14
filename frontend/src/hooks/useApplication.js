import { useState, useEffect, useCallback } from 'react';
import { appClient } from '../api/appClient';

export function useApplication(id) {
    const [application, setApplication] = useState(null);
    const [loading, setLoading] = useState(false);

    const fetchApplication = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        try {
            const res = await appClient.get(`/applications/${id}`);
            setApplication(res.data);
        } catch (err) {
            console.error("Failed to fetch application", err);
            setApplication(null);
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchApplication();
    }, [fetchApplication]);

    return { application, loading, refresh: fetchApplication };
}
