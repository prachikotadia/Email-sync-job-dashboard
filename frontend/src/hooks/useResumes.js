import { useState, useEffect } from 'react';
import { appClient } from '../api/appClient';

export function useResumes() {
    const [resumes, setResumes] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchResumes = async () => {
            setLoading(true);
            try {
                const res = await appClient.get('/resumes');
                setResumes(res.data);
            } catch (err) {
                console.error("Failed to fetch resumes", err);
                setResumes([]);
            } finally {
                setLoading(false);
            }
        };

        fetchResumes();
    }, []);

    return { resumes, loading };
}
