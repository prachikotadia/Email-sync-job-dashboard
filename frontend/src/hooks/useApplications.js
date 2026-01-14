import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';

export function useApplications(filters = {}) {
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchApplications = async () => {
        setLoading(true);
        try {
            const res = await appClient.get('/applications', { params: filters });
            // Filter out applications with invalid statuses (safety check)
            const validStatuses = ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer", 
                                 "Screening", "Interview (R1)", "Interview (R2)", "Interview (Final)",
                                 "Offer", "Accepted", "Hired"];
            const filtered = (res.data || []).filter(app => {
                const status = app.status || "";
                // Check if status is valid
                const isValid = validStatuses.includes(status) || 
                               status.includes("Interview") ||  // Allow Interview variations
                               ["Offer", "Accepted", "Hired"].includes(status);
                return isValid && status !== "Unknown";
            });
            setApplications(filtered);
        } catch (err) {
            console.error("Failed to fetch applications", err);
            setApplications([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchApplications();
    }, [JSON.stringify(filters)]);

    return { applications, loading, refresh: fetchApplications };
}
