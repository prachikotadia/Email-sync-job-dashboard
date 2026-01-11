const REQUIRED_VARS = [
    'VITE_API_GATEWAY_URL'
];

function validateEnv() {
    const missing = REQUIRED_VARS.filter(key => !import.meta.env[key]);
    if (missing.length > 0) {
        console.warn(`Missing required env vars: ${missing.join(', ')}. App may default to Demo Mode.`);
        return false;
    }
    return true;
}

export const env = {
    // API Gateway is the main entry point for all backend requests
    API_GATEWAY_URL: import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000',
    // Legacy support (optional, for backward compatibility)
    EMAIL_AI_URL: import.meta.env.VITE_EMAIL_AI_BASE_URL || 'http://localhost:8001',
    APP_API_URL: import.meta.env.VITE_APP_BASE_URL || 'http://localhost:8002',
    IS_DEV: import.meta.env.DEV,
    isValid: validateEnv()
};
