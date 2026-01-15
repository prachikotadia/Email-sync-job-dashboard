import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoInput } from '../ui/NeoInput';
import { NeoSelect } from '../ui/NeoInput';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, User, UserCircle } from 'lucide-react';
import { env } from '../config/env';

export default function Login() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const { login, register, isLoading, handleGoogleCallback } = useAuth();
    
    const [mode, setMode] = useState('login'); // 'login' or 'register'
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [role, setRole] = useState('viewer');
    const [errors, setErrors] = useState({});
    const [submitting, setSubmitting] = useState(false);
    const [processingGoogleCallback, setProcessingGoogleCallback] = useState(false); // Prevent duplicate processing
    const [googleEnabled, setGoogleEnabled] = useState(true);
    const [googleStatusMsg, setGoogleStatusMsg] = useState('');

    // Detect if Google OAuth is configured server-side (avoid hard-failing with 500s)
    // Use useRef to prevent React StrictMode double-invocation
    const hasCheckedGoogle = useRef(false);
    
    useEffect(() => {
        // Guard against double-call in React StrictMode
        if (hasCheckedGoogle.current) return;
        hasCheckedGoogle.current = true;
        
        let cancelled = false;
        const checkGoogle = async () => {
            try {
                // Try API Gateway first, fallback to auth service directly if 405
                let res = await fetch(`${env.API_GATEWAY_URL}/auth/google/status`, {
                    credentials: 'include',  // Include credentials for CORS
                });
                
                if (!res.ok && res.status === 405) {
                    // Workaround: API Gateway route issue, call auth service directly
                    res = await fetch('http://localhost:8003/auth/google/status', {
                        credentials: 'include',
                    });
                }
                
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                
                // Safely parse JSON - handle empty/invalid responses
                let data;
                try {
                    const text = await res.text();
                    if (!text || text.trim() === '') {
                        throw new Error('Empty response');
                    }
                    data = JSON.parse(text);
                } catch (parseError) {
                    console.error('Failed to parse status response:', parseError);
                    // Use safe defaults
                    data = {
                        isAuthenticated: false,
                        hasAccessToken: false,
                        hasRefreshToken: false,
                        user: null,
                        configured: false,
                    };
                }
                
                if (cancelled) return;
                
                // Use stable schema fields
                const configured = data?.configured ?? data?.isAuthenticated ?? false;
                setGoogleEnabled(configured);
                
                if (!configured) {
                    setGoogleStatusMsg('Google login is not configured on the server');
                } else {
                    setGoogleStatusMsg('');
                }
            } catch (e) {
                // If the endpoint isn't available or gateway is down, use safe defaults
                if (cancelled) return;
                console.warn('Google status check failed:', e);
                // Default to enabled but show no message (graceful degradation)
                setGoogleEnabled(true);
                setGoogleStatusMsg('');
            }
        };
        
        checkGoogle();
        return () => { cancelled = true; };
    }, []);

    // Handle Google OAuth callback
    useEffect(() => {
        const accessToken = searchParams.get('access_token');
        const refreshToken = searchParams.get('refresh_token');
        const googleLogin = searchParams.get('google_login');
        const googleError = searchParams.get('google_error');

        console.log('Login component - Checking Google callback params:', {
            hasAccessToken: !!accessToken,
            hasRefreshToken: !!refreshToken,
            googleLogin,
            googleError,
            hasCallback: !!handleGoogleCallback
        });

        if (googleError) {
            // Only log non-critical errors (ignore scope change warnings from Google OAuth library)
            if (googleError !== 'scope_changed' && !googleError.includes('Scope has changed')) {
                console.error('Google OAuth error:', googleError);
                // Show user-friendly error message
                const decodedError = decodeURIComponent(googleError);
                if (decodedError.includes('Access denied') || decodedError.includes('testing mode')) {
                    alert(
                        'Google Login Error\n\n' +
                        'This app is in testing mode. To sign in:\n\n' +
                        '1. Go to Google Cloud Console\n' +
                        '2. Navigate to: APIs & Services → OAuth consent screen\n' +
                        '3. Scroll to "Test users" section\n' +
                        '4. Click "+ ADD USERS"\n' +
                        '5. Add your email: prachicagoo@gmail.com\n' +
                        '6. Try signing in again\n\n' +
                        'Or use email/password login below.'
                    );
                } else {
                    alert(`Google Login Error: ${decodedError}`);
                }
            }
            // Clean up URL params
            searchParams.delete('google_error');
            setSearchParams(searchParams, { replace: true });
            return;
        }

        if (googleLogin === 'true' && accessToken && refreshToken && !processingGoogleCallback) {
            console.log('Processing Google login callback...');
            setProcessingGoogleCallback(true);
            
            // Handle Google OAuth callback
            if (handleGoogleCallback) {
                handleGoogleCallback(accessToken, refreshToken, searchParams)
                    .then((userInfo) => {
                        console.log('Google callback successful, user:', userInfo);
                        
                        // Clean up URL params FIRST
                        const newParams = new URLSearchParams(searchParams);
                        newParams.delete('access_token');
                        newParams.delete('refresh_token');
                        newParams.delete('google_login');
                        newParams.delete('user_id');
                        newParams.delete('email');
                        setSearchParams(newParams, { replace: true });
                        
                        // Navigate to dashboard - use window.location for reliable redirect
                        console.log('Navigating to dashboard...');
                        // Use window.location for more reliable redirect
                        setTimeout(() => {
                            window.location.href = '/dashboard';
                        }, 100);
                    })
                    .catch((error) => {
                        console.error('Google callback error:', error);
                        setProcessingGoogleCallback(false);
                        // Show error to user
                        alert(`Failed to complete Google login: ${error.message || 'Unknown error'}. Please try again.`);
                    });
            } else {
                console.error('handleGoogleCallback is not available');
                setProcessingGoogleCallback(false);
                alert('Google login callback handler not available. Please refresh the page.');
            }
        }
    }, [searchParams, setSearchParams, navigate, handleGoogleCallback]);

    const validateForm = () => {
        const newErrors = {};
        
        if (!email) {
            newErrors.email = 'Email is required';
        } else if (!/\S+@\S+\.\S+/.test(email)) {
            newErrors.email = 'Email is invalid';
        }
        
        if (!password) {
            newErrors.password = 'Password is required';
        } else if (password.length < 8) {
            newErrors.password = 'Password must be at least 8 characters';
        }
        
        if (mode === 'register' && fullName && fullName.trim().length > 255) {
            newErrors.fullName = 'Full name must be less than 255 characters';
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }

        setSubmitting(true);
        try {
            if (mode === 'login') {
                await login(email, password);
                navigate('/dashboard');
            } else {
                await register(email, password, fullName.trim() || undefined, role);
                // After successful registration, switch to login mode
                setMode('login');
                setPassword('');
                setFullName('');
                setErrors({});
            }
        } catch (error) {
            // Error handling is done in AuthContext via toast
            console.error(`${mode} error:`, error);
        } finally {
            setSubmitting(false);
        }
    };

    const switchMode = () => {
        setMode(mode === 'login' ? 'register' : 'login');
        setErrors({});
        setPassword('');
        setFullName('');
    };

    return (
        <div className="min-h-screen bg-app flex flex-col justify-center py-12 sm:px-6 lg:px-8">
            <div className="sm:mx-auto sm:w-full sm:max-w-md">
                <div className="flex justify-center mb-6">
                    <div className="h-16 w-16 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-neo-button">
                        <span className="text-white font-bold text-3xl">J</span>
                    </div>
                </div>
                <h2 className="text-center text-3xl font-extrabold text-text-primary tracking-tight">
                    JobPulse AI
                </h2>
                <p className="mt-2 text-center text-sm text-text-secondary">
                    Your AI-powered job application tracker
                </p>
            </div>

            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <NeoCard className="py-8 px-4 sm:px-10">
                    <div className="mb-6">
                        <div className="flex rounded-xl bg-slate-100 dark:bg-white/5 p-1 border border-white/20 dark:border-white/5">
                            <button
                                type="button"
                                onClick={() => mode !== 'login' && switchMode()}
                                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                                    mode === 'login'
                                        ? 'bg-surface text-text-primary shadow-sm'
                                        : 'text-text-secondary hover:text-text-primary'
                                }`}
                            >
                                Login
                            </button>
                            <button
                                type="button"
                                onClick={() => mode !== 'register' && switchMode()}
                                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                                    mode === 'register'
                                        ? 'bg-surface text-text-primary shadow-sm'
                                        : 'text-text-secondary hover:text-text-primary'
                                }`}
                            >
                                Register
                            </button>
                        </div>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-text-primary mb-2">
                                Email Address
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Mail className="h-5 w-5 text-text-muted" />
                                </div>
                                <NeoInput
                                    id="email"
                                    type="email"
                                    autoComplete="email"
                                    placeholder="you@example.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    error={errors.email}
                                    className="pl-10"
                                    disabled={submitting}
                                />
                            </div>
                        </div>

                        {mode === 'register' && (
                            <div>
                                <label htmlFor="fullName" className="block text-sm font-medium text-text-primary mb-2">
                                    Full Name (Optional)
                                </label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <UserCircle className="h-5 w-5 text-text-muted" />
                                    </div>
                                    <NeoInput
                                        id="fullName"
                                        type="text"
                                        autoComplete="name"
                                        placeholder="John Doe"
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        error={errors.fullName}
                                        className="pl-10"
                                        disabled={submitting}
                                    />
                                </div>
                            </div>
                        )}

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-text-primary mb-2">
                                Password
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock className="h-5 w-5 text-text-muted" />
                                </div>
                                <NeoInput
                                    id="password"
                                    type="password"
                                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    error={errors.password}
                                    className="pl-10"
                                    disabled={submitting}
                                />
                            </div>
                            {mode === 'register' && (
                                <p className="mt-1 text-xs text-text-muted">
                                    Must be at least 8 characters
                                </p>
                            )}
                        </div>

                        {mode === 'register' && (
                            <div>
                                <label htmlFor="role" className="block text-sm font-medium text-text-primary mb-2">
                                    Role (Optional)
                                </label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <User className="h-5 w-5 text-text-muted" />
                                    </div>
                                    <NeoSelect
                                        id="role"
                                        value={role}
                                        onChange={(e) => setRole(e.target.value)}
                                        className="pl-10"
                                        disabled={submitting}
                                    >
                                        <option value="viewer">Viewer (Read-only)</option>
                                        <option value="editor">Editor (Full access)</option>
                                    </NeoSelect>
                                </div>
                                <p className="mt-1 text-xs text-text-muted">
                                    First user will automatically get Editor role
                                </p>
                            </div>
                        )}

                        <div>
                            <NeoButton
                                type="submit"
                                loading={submitting}
                                disabled={submitting || isLoading}
                                className="w-full flex justify-center py-3 text-base"
                            >
                                {mode === 'login' ? 'Sign in' : 'Create Account'}
                            </NeoButton>
                        </div>
                    </form>

                    <div className="mt-6">
                        <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-white/20 dark:border-white/5" />
                            </div>
                            <div className="relative flex justify-center text-sm">
                                <span className="px-3 bg-surface text-text-muted">Or continue with</span>
                            </div>
                        </div>

                        <div className="mt-6">
                            <NeoButton
                                variant="secondary"
                                disabled={!googleEnabled}
                                onClick={() => {
                                    if (!googleEnabled) return;
                                    // WORKAROUND: Call auth service directly due to API Gateway 405 errors
                                    // The API Gateway routes for /auth/google/* are not working properly
                                    // Using auth service directly ensures Google login works
                                    const authServiceUrl = 'http://localhost:8003/auth/google/login';
                                    window.location.href = authServiceUrl;
                                }}
                                className="w-full inline-flex justify-center items-center py-3"
                            >
                                <svg className="h-5 w-5 mr-2" aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .533 5.333.533 12S5.867 24 12.48 24c3.44 0 6.1-1.12 7.853-2.933 1.787-1.84 2.32-4.427 2.32-6.502 0-.64-.067-1.28-.187-1.889H12.48z" />
                                </svg>
                                Continue with Google
                            </NeoButton>
                            {!googleEnabled && googleStatusMsg ? (
                                <p className="mt-2 text-xs text-text-muted text-center">
                                    {googleStatusMsg}
                                </p>
                            ) : null}
                        </div>
                    </div>
                </NeoCard>
            </div>
        </div>
    );
}