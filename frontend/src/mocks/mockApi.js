import { MOCK_APPLICATIONS, MOCK_METRICS, MOCK_ACTIVITY, MOCK_RESUMES } from './seed';

export const mockApi = {
    login: async () => {
        await delay(500);
        return { token: 'mock-token', user: { name: 'Demo User', email: 'demo@example.com' } };
    },
    getApplications: async () => {
        await delay(800);
        return MOCK_APPLICATIONS;
    },
    getApplication: async (id) => {
        await delay(300);
        return MOCK_APPLICATIONS.find(a => a.id === id);
    },
    getMetrics: async () => {
        await delay(400);
        return MOCK_METRICS;
    },
    getRecentActivity: async () => {
        await delay(300);
        return MOCK_ACTIVITY;
    },
    getResumes: async () => {
        await delay(500);
        return MOCK_RESUMES;
    },
    syncGmail: async () => {
        await delay(2000);
        return { success: true, count: 5 };
    },
    confirmApplication: async (id, status) => {
        await delay(500);
        return { success: true };
    }
};

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
