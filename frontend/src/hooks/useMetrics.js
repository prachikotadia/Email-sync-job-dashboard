import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';

export function useMetrics() {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchMetrics = async () => {
            setLoading(true);
            try {
                const res = await appClient.get('/metrics');
                setMetrics(res.data);
            } catch (err) {
                console.error("Failed to fetch metrics", err);
                setMetrics(null);
            } finally {
                setLoading(false);
            }
        };

        fetchMetrics();
    }, []);

    return { metrics, loading };
}
