const REQUIRED_VARS = [
    'VITE_EMAIL_AI_BASE_URL',
    'VITE_APP_BASE_URL'
];

function validateEnv() {
    const missing = REQUIRED_VARS.filter(key => !import.meta.env[key]);
    if (missing.length > 0) {
        // We throw an error that can be caught by a global error boundary or just handled
        // For now, we will log a warning and return default mock values or mock mode trigger
        console.warn(`Missing required env vars: ${missing.join(', ')}. App may default to Demo Mode.`);
        return false;
    }
    return true;
}

export const env = {
    EMAIL_AI_URL: import.meta.env.VITE_EMAIL_AI_BASE_URL || 'http://localhost:8001',
    APP_API_URL: import.meta.env.VITE_APP_BASE_URL || 'http://localhost:8002',
    IS_DEV: import.meta.env.DEV,
    isValid: validateEnv()
};
