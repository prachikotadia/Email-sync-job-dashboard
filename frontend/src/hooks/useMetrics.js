import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';
import { mockApi } from '../mocks/mockApi';
import { useDemoMode } from './useDemoMode';

export function useMetrics() {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const { isDemoMode, enableDemoMode } = useDemoMode();

    useEffect(() => {
        const fetchMetrics = async () => {
            setLoading(true);
            try {
                if (isDemoMode) {
                    const data = await mockApi.getMetrics();
                    setMetrics(data);
                } else {
                    const res = await appClient.get('/metrics');
                    setMetrics(res.data);
                }
            } catch (err) {
                if (!isDemoMode) {
                    enableDemoMode();
                    const data = await mockApi.getMetrics();
                    setMetrics(data);
                }
            } finally {
                setLoading(false);
            }
        };

        fetchMetrics();
    }, [isDemoMode]);

    return { metrics, loading };
}
