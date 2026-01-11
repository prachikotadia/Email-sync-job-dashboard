import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/authService';
import { useToast } from './ToastContext';

const AuthContext = createContext();

const ACCESS_TOKEN_KEY = 'auth_access_token';
const REFRESH_TOKEN_KEY = 'auth_refresh_token';
const USER_KEY = 'auth_user';

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [accessToken, setAccessToken] = useState(null);
    const [refreshToken, setRefreshToken] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const { addToast } = useToast();

    // Helper function to clear auth (defined early to avoid dependency issues)
    const clearAuth = useCallback(() => {
        setUser(null);
        setAccessToken(null);
        setRefreshToken(null);
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }, []);

    // Refresh token handler
    const handleRefreshToken = useCallback(async (currentRefreshToken) => {
        if (!currentRefreshToken) {
            clearAuth();
            return null;
        }

        try {
            const response = await authService.refreshToken(currentRefreshToken);
            setAccessToken(response.access_token);
            localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
            
            // Update refresh token if provided
            if (response.refresh_token) {
                setRefreshToken(response.refresh_token);
                localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
            }
            return response.access_token;
        } catch (error) {
            console.error('Token refresh failed:', error);
            clearAuth();
            throw error;
        }
    }, [clearAuth]);

    // Initialize auth state from localStorage
    useEffect(() => {
        const initAuth = async () => {
            try {
                const storedAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
                const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
                const storedUser = localStorage.getItem(USER_KEY);

                if (storedAccessToken && storedRefreshToken && storedUser) {
                    setAccessToken(storedAccessToken);
                    setRefreshToken(storedRefreshToken);
                    setUser(JSON.parse(storedUser));
                    // Verify token is still valid by fetching user info
                    try {
                        const userInfo = await authService.getMe(storedAccessToken);
                        setUser(userInfo);
                        localStorage.setItem(USER_KEY, JSON.stringify(userInfo));
                    } catch (error) {
                        // Token invalid, try refresh
                        if (storedRefreshToken) {
                            await handleRefreshToken(storedRefreshToken);
                        } else {
                            clearAuth();
                        }
                    }
                }
            } catch (error) {
                console.error('Auth initialization error:', error);
                clearAuth();
            } finally {
                setIsLoading(false);
            }
        };

        initAuth();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Listen for logout events from API interceptor
    useEffect(() => {
        const handleLogoutEvent = () => {
            clearAuth();
        };
        
        window.addEventListener('auth:logout', handleLogoutEvent);
        return () => window.removeEventListener('auth:logout', handleLogoutEvent);
    }, [clearAuth]);

    // Auto-refresh token before expiration
    useEffect(() => {
        if (!accessToken || !refreshToken) return;

        // Refresh token periodically (every 10 minutes)
        const refreshInterval = setInterval(async () => {
            try {
                await handleRefreshToken(refreshToken);
            } catch (error) {
                console.error('Auto-refresh failed:', error);
            }
        }, 10 * 60 * 1000); // Check every 10 minutes

        return () => clearInterval(refreshInterval);
    }, [accessToken, refreshToken, handleRefreshToken]);

    const login = useCallback(async (email, password) => {
        try {
            const response = await authService.login(email, password);
            
            setAccessToken(response.access_token);
            setRefreshToken(response.refresh_token);
            setUser(response.user);
            
            localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
            localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
            localStorage.setItem(USER_KEY, JSON.stringify(response.user));
            
            addToast('Logged in successfully', 'success');
            return response;
        } catch (error) {
            const message = error.response?.data?.error?.message || error.message || 'Login failed';
            addToast(message, 'error');
            throw error;
        }
    }, [addToast]);

    const register = useCallback(async (email, password, fullName, role) => {
        try {
            const response = await authService.register(email, password, fullName, role);
            addToast('Account created successfully! Please login.', 'success');
            return response;
        } catch (error) {
            const message = error.response?.data?.error?.message || error.message || 'Registration failed';
            addToast(message, 'error');
            throw error;
        }
    }, [addToast]);

    const logout = useCallback(async () => {
        try {
            if (refreshToken && accessToken) {
                await authService.logout(accessToken, refreshToken);
            }
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            clearAuth();
            addToast('Logged out successfully', 'success');
        }
    }, [accessToken, refreshToken, addToast, clearAuth]);

    const handleGoogleCallback = useCallback(async (accessTokenParam, refreshTokenParam, searchParams) => {
        console.log('AuthContext - handleGoogleCallback called', {
            hasAccessToken: !!accessTokenParam,
            hasRefreshToken: !!refreshTokenParam,
            userId: searchParams?.get('user_id'),
            email: searchParams?.get('email')
        });
        
        try {
            const userId = searchParams?.get('user_id');
            const email = searchParams?.get('email');
            
            console.log('Setting tokens and fetching user info...');
            
            // Set tokens FIRST
            setAccessToken(accessTokenParam);
            setRefreshToken(refreshTokenParam);
            localStorage.setItem(ACCESS_TOKEN_KEY, accessTokenParam);
            localStorage.setItem(REFRESH_TOKEN_KEY, refreshTokenParam);
            
            // Fetch user info
            console.log('Fetching user info from API...');
            const userInfo = await authService.getMe(accessTokenParam);
            console.log('User info received:', userInfo);
            
            // Set user AFTER fetching (this will trigger isAuthenticated to become true)
            setUser(userInfo);
            localStorage.setItem(USER_KEY, JSON.stringify(userInfo));
            
            console.log('Google callback completed successfully, auth state updated');
            addToast('Logged in with Google successfully! Gmail connected.', 'success');
            
            // Return user info for navigation
            return userInfo;
        } catch (error) {
            console.error('Google callback error in AuthContext:', error);
            console.error('Error details:', {
                message: error.message,
                response: error.response?.data,
                status: error.response?.status
            });
            clearAuth();
            addToast(`Failed to complete Google login: ${error.message || 'Unknown error'}`, 'error');
            throw error;
        }
    }, [addToast, clearAuth]);

    const isAuthenticated = !!accessToken && !!user;

    const value = {
        user,
        accessToken,
        refreshToken,
        isLoading,
        isAuthenticated,
        login,
        register,
        logout,
        handleGoogleCallback,
        refreshTokenHandler: handleRefreshToken,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}