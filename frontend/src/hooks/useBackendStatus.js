import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';
import { env } from '../config/env';

export function useBackendStatus(autoCheck = true, interval = 30000) {
    const [status, setStatus] = useState({
        gateway: null,
        authService: null,
        isLoading: true,
        lastChecked: null,
    });

    const checkBackendStatus = useCallback(async () => {
        setStatus(prev => ({ ...prev, isLoading: true }));
        
        try {
            // Check API Gateway
            const gatewayResponse = await apiClient.get('/health', {
                timeout: 5000,
            }).catch(() => null);

            const gatewayStatus = gatewayResponse?.status === 200;

            // Check Auth Service through Gateway (try /auth/me which doesn't require auth for health)
            // Or we can check auth-service directly if it's exposed
            let authServiceStatus = null;
            try {
                // Try to check auth service health through gateway
                // Since we're using the gateway, if gateway is up, auth service should be accessible
                // But we can't directly check auth-service from frontend (it's internal)
                // So we'll infer from gateway status for now
                authServiceStatus = gatewayStatus; // If gateway works, auth service should work
            } catch (error) {
                authServiceStatus = false;
            }

            setStatus({
                gateway: gatewayStatus,
                authService: authServiceStatus,
                isLoading: false,
                lastChecked: new Date(),
            });

            return {
                gateway: gatewayStatus,
                authService: authServiceStatus,
            };
        } catch (error) {
            console.error('Backend status check failed:', error);
            setStatus({
                gateway: false,
                authService: false,
                isLoading: false,
                lastChecked: new Date(),
            });
            return {
                gateway: false,
                authService: false,
            };
        }
    }, []);

    useEffect(() => {
        if (autoCheck) {
            // Initial check
            checkBackendStatus();

            // Set up interval for periodic checks
            const intervalId = setInterval(checkBackendStatus, interval);

            return () => clearInterval(intervalId);
        }
    }, [autoCheck, interval, checkBackendStatus]);

    return {
        ...status,
        checkBackendStatus,
        isConnected: status.gateway === true && status.authService === true,
    };
}