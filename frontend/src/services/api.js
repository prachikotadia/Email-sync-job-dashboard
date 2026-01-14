import axios from 'axios';
import { env } from '../config/env';

// All API calls go through the API Gateway
export const apiClient = axios.create({
    baseURL: env.API_GATEWAY_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor for Auth - adds Bearer token from localStorage
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

// Response interceptor - handles 401 and token refresh
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // Handle 401 Unauthorized - try to refresh token
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                const refreshToken = localStorage.getItem('auth_refresh_token');
                if (!refreshToken) {
                    throw new Error('No refresh token available');
                }

                // Import authService dynamically to avoid circular dependency
                const { authService } = await import('./authService');
                const response = await authService.refreshToken(refreshToken);

                // Update tokens in localStorage
                localStorage.setItem('auth_access_token', response.access_token);
                if (response.refresh_token) {
                    localStorage.setItem('auth_refresh_token', response.refresh_token);
                }

                // Update the original request with new token
                originalRequest.headers.Authorization = `Bearer ${response.access_token}`;

                // Retry the original request
                return apiClient(originalRequest);
            } catch (refreshError) {
                // Refresh failed - clear auth and redirect to login
                localStorage.removeItem('auth_access_token');
                localStorage.removeItem('auth_refresh_token');
                localStorage.removeItem('auth_user');
                
                // Dispatch event to trigger logout in AuthContext
                window.dispatchEvent(new CustomEvent('auth:logout'));
                
                // Only redirect if not already on login page
                if (!window.location.pathname.startsWith('/') || window.location.pathname !== '/') {
                    window.location.href = '/';
                }
                
                return Promise.reject(refreshError);
            }
        }

        // Trigger demo mode on network error or server error (only if not auth-related)
        if ((!error.response || error.response.status >= 500) && error.response?.status !== 401) {
            window.dispatchEvent(new Event('demo-mode-trigger'));
        }

        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

// Legacy exports for backward compatibility
export const emailAiClient = apiClient;
export const appClient = apiClient;

// Health check - now uses API Gateway
export const checkHealth = async () => {
    try {
        const gatewayHealth = await apiClient.get('/health', { timeout: 15000 }).catch(() => ({ status: 500 }));
        const isGatewayHealthy = gatewayHealth.status === 200;
        
        return {
            gateway: isGatewayHealthy,
            authService: isGatewayHealthy, // Auth service accessible through gateway
            emailService: isGatewayHealthy, // Gateway proxies to services
            appService: isGatewayHealthy,   // Gateway proxies to services
        };
    } catch (e) {
        return { 
            gateway: false, 
            authService: false,
            emailService: false, 
            appService: false 
        };
    }
};
