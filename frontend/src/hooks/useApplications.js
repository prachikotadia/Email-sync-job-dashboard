import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';
import { useAuth } from '../context/AuthContext';

export function useApplications(filters = {}) {
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const { isAuthenticated } = useAuth();

    const fetchApplications = async () => {
        // Don't fetch if not authenticated
        if (!isAuthenticated) {
            setLoading(false);
            setApplications([]);
            return;
        }

        setLoading(true);
        try {
            const res = await appClient.get('/applications', { params: filters });
            console.log("📥 useApplications - API Response:", res.data);
            // Ensure res.data is an array
            const data = Array.isArray(res.data) ? res.data : [];
            console.log("📥 useApplications - Data array length:", data.length);
            console.log("📊 [FRONTEND DATA FLOW] Received from API: ", data.length, "applications");
            console.log("📊 [FRONTEND DATA FLOW] NO LIMIT applied - showing ALL applications");
            
            // Show ALL applications - don't filter by status
            // Only filter out invalid/null objects
            const filtered = data.filter(app => {
                if (!app || typeof app !== 'object') return false;
                // Accept all applications regardless of status
                return true;
            });
            console.log("📥 useApplications - Filtered applications:", filtered.length);
            console.log("📊 [FRONTEND DATA FLOW] After filtering invalid objects: ", filtered.length, "applications");
            console.log("📥 useApplications - Applications:", filtered);
            setApplications(filtered);
        } catch (err) {
            // Silently handle auth errors (401/403) - user might not be logged in
            if (err.response?.status === 401 || err.response?.status === 403) {
                setApplications([]);
                return;
            }
            
            // Silently handle server errors - service might be down
            // Don't spam console with errors
            setApplications([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!isAuthenticated) {
            setApplications([]);
            setLoading(false);
            return;
        }
        
        let cancelled = false;
        const doFetch = async () => {
            await fetchApplications();
            if (cancelled) {
                setApplications([]);
            }
        };
        
        doFetch();
        
        return () => {
            cancelled = true;
        };
    }, [isAuthenticated, JSON.stringify(filters)]);

    return { applications, loading, refresh: fetchApplications };
}
