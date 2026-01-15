import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';
import { useAuth } from '../context/AuthContext';

export function useMetrics() {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const { isAuthenticated } = useAuth();

    useEffect(() => {
        // Only fetch metrics if user is authenticated
        if (!isAuthenticated) {
            setLoading(false);
            setMetrics(null);
            return;
        }

        let cancelled = false;
        const fetchMetrics = async () => {
            setLoading(true);
            try {
                const res = await appClient.get('/metrics');
                if (cancelled) return;
                
                // Ensure response.data is a valid object
                if (res.data && typeof res.data === 'object') {
                    setMetrics(res.data);
                } else {
                    console.error('Invalid metrics data received:', res.data);
                    setMetrics(null);
                }
            } catch (err) {
                if (cancelled) return;
                
                // Silently handle auth errors (401/403) - user might not be logged in
                if (err.response?.status === 401 || err.response?.status === 403) {
                    setMetrics(null);
                    return;
                }
                
                // Silently handle all errors - don't spam console
                // Errors are expected if service is down or user not authenticated
                setMetrics(null);
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        fetchMetrics();
        
        return () => {
            cancelled = true;
        };
    }, [isAuthenticated]);

    return { metrics, loading };
}
