import axios from 'axios';
import { env } from '../config/env';

const gmailClient = axios.create({
    baseURL: env.API_GATEWAY_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth token interceptor
gmailClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    } else {
        // No token available - this request will fail, but we'll handle it in response interceptor
        console.warn('No authentication token found for Gmail service request');
    }
    return config;
});

// Handle 401 Unauthorized errors - redirect to login
gmailClient.interceptors.response.use(
    response => response,
    error => {
        if (error.response?.status === 401) {
            // User is not authenticated - dispatch logout event
            console.warn('Gmail service request unauthorized - redirecting to login');
            window.dispatchEvent(new CustomEvent('auth:logout'));
            // Redirect to login page
            if (window.location.pathname !== '/') {
                window.location.href = '/';
            }
        }
        return Promise.reject(error);
    }
);

export const gmailService = {
    /**
     * Get Gmail OAuth authorization URL
     */
    async getAuthUrl() {
        const response = await gmailClient.get('/gmail/auth/url');
        return response.data;
    },

    /**
     * Get Gmail connection status
     */
    async getStatus() {
        const response = await gmailClient.get('/gmail/status');
        return response.data;
    },

    /**
     * Disconnect Gmail account
     */
    async disconnect() {
        const response = await gmailClient.post('/gmail/disconnect');
        return response.data;
    },

    /**
     * Sync emails from Gmail
     */
    async sync() {
        const response = await gmailClient.post('/gmail/sync');
        return response.data;
    },

    /**
     * Get Gmail token scopes (debug endpoint - dev only)
     */
    async getScopes() {
        const response = await gmailClient.get('/debug/gmail/scopes');
        return response.data;
    },
};

export default gmailService;