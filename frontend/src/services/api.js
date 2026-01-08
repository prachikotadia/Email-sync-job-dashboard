import axios from 'axios';
import { env } from '../config/env';

export const emailAiClient = axios.create({
    baseURL: env.EMAIL_AI_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const appClient = axios.create({
    baseURL: env.APP_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor for Auth
const authInterceptor = (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
};

emailAiClient.interceptors.request.use(authInterceptor);
appClient.interceptors.request.use(authInterceptor);

// Response interceptor
const errorInterceptor = (error) => {
    // Global error handling
    if (error.response?.status === 401) {
        // Redirect to login if unauthorized
        // In a real app, you might use a custom event or context to trigger this
        if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/')) {
            console.warn('Unauthorized access, redirecting to login...');
            // window.location.href = '/'; 
        }
    }
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
};

emailAiClient.interceptors.response.use((r) => r, errorInterceptor);
appClient.interceptors.response.use((r) => r, errorInterceptor);

export const checkHealth = async () => {
    try {
        const emailHealth = await emailAiClient.get('/health').catch(() => ({ status: 500 }));
        const appHealth = await appClient.get('/health').catch(() => ({ status: 500 }));
        return {
            emailService: emailHealth.status === 200,
            appService: appHealth.status === 200
        };
    } catch (e) {
        return { emailService: false, appService: false };
    }
};
