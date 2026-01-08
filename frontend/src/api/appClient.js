import axios from 'axios';
import { env } from '../config/env';

export const appClient = axios.create({
    baseURL: env.APP_API_URL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
});

appClient.interceptors.response.use(
    response => response,
    error => {
        // Trigger demo mode on network error or server error
        if (!error.response || error.response.status >= 500) {
            window.dispatchEvent(new Event('demo-mode-trigger'));
        }
        return Promise.reject(error);
    }
);
