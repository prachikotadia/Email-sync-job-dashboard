import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';
import { mockApi } from '../mocks/mockApi';
import { useDemoMode } from './useDemoMode';
import { useToast } from '../context/ToastContext';

export function useApplications(filters = {}) {
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const { isDemoMode, enableDemoMode } = useDemoMode();
    const { addToast } = useToast();

    const fetchApplications = async () => {
        setLoading(true);
        try {
            if (isDemoMode) {
                const data = await mockApi.getApplications();
                setApplications(data); // Filter logic usually happens backend or component side. 
                // For mock, we'll return all and let component filter or implement simple filter here.
            } else {
                const res = await appClient.get('/applications', { params: filters });
                setApplications(res.data);
            }
        } catch (err) {
            console.error("Failed to fetch applications", err);
            // Fallback to demo mode
            if (!isDemoMode) {
                enableDemoMode();
                addToast("Backend unavailable. Switching to Demo Mode.", "warning");
                const data = await mockApi.getApplications();
                setApplications(data);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchApplications();
    }, [isDemoMode, JSON.stringify(filters)]);

    return { applications, loading, refresh: fetchApplications };
}
