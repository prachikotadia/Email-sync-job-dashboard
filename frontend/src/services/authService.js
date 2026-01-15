import axios from 'axios';
import { env } from '../config/env';

const authClient = axios.create({
    baseURL: env.API_GATEWAY_URL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
});

/**
 * Register a new user account
 * @param {string} email - User email
 * @param {string} password - User password (min 8 chars)
 * @param {string} [fullName] - Optional full name
 * @param {string} [role] - Optional role: 'viewer' or 'editor'
 * @returns {Promise<{message: string, user: {id: string, email: string, full_name: string, role: string}}>}
 */
export const authService = {
    async register(email, password, fullName, role) {
        const response = await authClient.post('/auth/register', {
            email,
            password,
            ...(fullName && { full_name: fullName }),
            ...(role && { role }),
        });
        return response.data;
    },

    /**
     * Login with email and password
     * @param {string} email - User email
     * @param {string} password - User password
     * @returns {Promise<{access_token: string, refresh_token: string, token_type: string, user: {id: string, email: string, role: string}}>}
     */
    async login(email, password) {
        const response = await authClient.post('/auth/login', {
            email,
            password,
        });
        return response.data;
    },

    /**
     * Refresh access token using refresh token
     * @param {string} refreshToken - Refresh token
     * @returns {Promise<{access_token: string, token_type: string}>}
     */
    async refreshToken(refreshToken) {
        const response = await authClient.post('/auth/refresh', {
            refresh_token: refreshToken,
        });
        return response.data;
    },

    /**
     * Logout and revoke refresh token
     * @param {string} accessToken - Current access token
     * @param {string} refreshToken - Refresh token to revoke
     * @returns {Promise<{message: string}>}
     */
    async logout(accessToken, refreshToken) {
        const response = await authClient.post(
            '/auth/logout',
            { refresh_token: refreshToken },
            {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                },
            }
        );
        return response.data;
    },

    /**
     * Get current authenticated user information
     * @param {string} accessToken - Current access token
     * @returns {Promise<{id: string, email: string, role: string}>}
     */
    async getMe(accessToken) {
        try {
            const response = await authClient.get('/auth/me', {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                },
            });
            // Ensure we always return a valid object, never undefined
            if (!response.data || typeof response.data !== 'object') {
                throw new Error('Invalid user data received from server');
            }
            return response.data;
        } catch (error) {
            // Log error for debugging
            console.error('getMe error:', error);
            // Re-throw with more context
            if (error.response?.status === 401) {
                throw new Error('Authentication failed. Please login again.');
            }
            throw error;
        }
    },
};