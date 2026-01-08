import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';
import { mockApi } from '../mocks/mockApi';
import { useDemoMode } from './useDemoMode';

export function useResumes() {
    const [resumes, setResumes] = useState([]);
    const [loading, setLoading] = useState(true);
    const { isDemoMode, enableDemoMode } = useDemoMode();

    useEffect(() => {
        const fetchResumes = async () => {
            setLoading(true);
            try {
                if (isDemoMode) {
                    const data = await mockApi.getResumes();
                    setResumes(data);
                } else {
                    const res = await appClient.get('/resumes');
                    setResumes(res.data);
                }
            } catch (err) {
                if (!isDemoMode) {
                    enableDemoMode();
                    const data = await mockApi.getResumes();
                    setResumes(data);
                }
            } finally {
                setLoading(false);
            }
        };

        fetchResumes();
    }, [isDemoMode]);

    return { resumes, loading };
}
