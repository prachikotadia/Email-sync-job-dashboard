import React, { useState, useEffect } from 'react';
import { Server, Shield, Save, Monitor, AlertTriangle, Moon, Sun, LogOut, User as UserIcon, RefreshCw, Mail, CheckCircle, X } from 'lucide-react';
import { checkHealth } from '../services/api';
import { gmailService } from '../services/gmailService';
import { useToast } from '../context/ToastContext';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { NeoInput } from '../ui/NeoInput';
import { NeoBadge } from '../ui/NeoBadge';
import { SyncProgress } from './SyncProgress';

export default function Settings() {
    const { addToast } = useToast();
    const { theme, toggleTheme } = useTheme();
    const { user, logout, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const [health, setHealth] = useState({ gateway: null, authService: null, emailService: null, appService: null });
    const [ghostedThreshold, setGhostedThreshold] = useState(14);
    const [gmailStatus, setGmailStatus] = useState({ is_connected: false, gmail_email: null, connected_at: null });
    const [isConnectingGmail, setIsConnectingGmail] = useState(false);
    const [isDisconnectingGmail, setIsDisconnectingGmail] = useState(false);
    const [isLoggingOut, setIsLoggingOut] = useState(false);
    const [isCheckingHealth, setIsCheckingHealth] = useState(false);
    const [isLoadingGmailStatus, setIsLoadingGmailStatus] = useState(true);
    const [redirectUri, setRedirectUri] = useState(null);
    const [isLoadingRedirectUri, setIsLoadingRedirectUri] = useState(false);
    const [tokenScopes, setTokenScopes] = useState(null);
    const [isLoadingScopes, setIsLoadingScopes] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);

    // Fetch redirect URI configuration
    const fetchRedirectUri = async () => {
        setIsLoadingRedirectUri(true);
        try {
            const apiUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000';
            const response = await fetch(`${apiUrl}/debug/oauth`);
            if (response.ok) {
                const data = await response.json();
                setRedirectUri(data.redirect_uri);
            } else {
                setRedirectUri(null);
            }
        } catch (error) {
            console.error('Failed to fetch redirect URI:', error);
            setRedirectUri(null);
        } finally {
            setIsLoadingRedirectUri(false);
        }
    };

    const fetchHealth = async () => {
        setIsCheckingHealth(true);
        try {
            const status = await checkHealth();
            setHealth(status);
        } catch (error) {
            console.error('Health check failed:', error);
            setHealth({ gateway: false, authService: false, emailService: false, appService: false });
        } finally {
            setIsCheckingHealth(false);
        }
    };

    // Fetch Gmail connection status
    const fetchGmailStatus = async () => {
        // Only fetch if user is authenticated
        if (!isAuthenticated || !user) {
            setIsLoadingGmailStatus(false);
            setGmailStatus({ is_connected: false, gmail_email: null, connected_at: null });
            return;
        }

        setIsLoadingGmailStatus(true);
        try {
            const status = await gmailService.getStatus();
            console.log('Gmail status received:', status);
            setGmailStatus(status);
        } catch (error) {
            // If 401, user is not authenticated - already handled by interceptor
            if (error.response?.status === 401) {
                console.warn('Unauthorized access to Gmail status - user not authenticated');
                setGmailStatus({ is_connected: false, gmail_email: null, connected_at: null });
                return;
            }
            console.error('Failed to fetch Gmail status:', error);
            setGmailStatus({ is_connected: false, gmail_email: null, connected_at: null });
        } finally {
            setIsLoadingGmailStatus(false);
        }
    };

    // Fetch Gmail token scopes (dev only)
    const fetchTokenScopes = async () => {
        if (!isAuthenticated || !user || !gmailStatus.is_connected) {
            setTokenScopes(null);
            return;
        }

        setIsLoadingScopes(true);
        try {
            const scopes = await gmailService.getScopes();
            setTokenScopes(scopes);
        } catch (error) {
            // Debug endpoint may not be available (not dev mode, or service error)
            console.warn('Failed to fetch token scopes:', error);
            setTokenScopes(null);
        } finally {
            setIsLoadingScopes(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        fetchRedirectUri(); // Fetch redirect URI on mount
        // Only fetch Gmail status if user is authenticated
        if (isAuthenticated && user) {
            fetchGmailStatus();
        }
    }, [isAuthenticated, user]); // Re-fetch when auth state changes

    // Fetch token scopes when Gmail is connected
    useEffect(() => {
        if (gmailStatus.is_connected) {
            fetchTokenScopes();
        } else {
            setTokenScopes(null);
        }
        // Refresh health status every 30 seconds
        const healthInterval = setInterval(fetchHealth, 30000);
        return () => {
            clearInterval(healthInterval);
        };
    }, [isAuthenticated, user]); // Re-fetch when auth state changes

    // Handle OAuth callback parameters
    useEffect(() => {
        const gmailConnected = searchParams.get('gmail_connected');
        const gmailError = searchParams.get('gmail_error');
        const errorDetails = searchParams.get('error_details');
        const email = searchParams.get('email');

        if (gmailConnected === 'true') {
            addToast(`Gmail connected successfully${email ? `: ${email}` : ''}`, 'success');
            fetchGmailStatus();
            // Clean up URL params
            searchParams.delete('gmail_connected');
            searchParams.delete('email');
            setSearchParams(searchParams);
        } else if (gmailError) {
            // Show detailed error message
            let errorMessage = `Gmail connection failed: ${gmailError}`;
            if (errorDetails) {
                const decodedDetails = decodeURIComponent(errorDetails);
                errorMessage += `\n\nDetails: ${decodedDetails}`;
                // Log to console for debugging
                console.error('Gmail OAuth Error Details:', decodedDetails);
            }
            addToast(errorMessage, 'error', 10000); // Show for 10 seconds for detailed errors
            // Clean up URL params
            searchParams.delete('gmail_error');
            searchParams.delete('error_details');
            setSearchParams(searchParams);
        }
    }, [searchParams, addToast, fetchGmailStatus, setSearchParams]);

    const handleConnectGmail = async () => {
        // Ensure user is authenticated before connecting Gmail
        if (!isAuthenticated || !user) {
            addToast('You must be logged in to connect Gmail account', 'error');
            navigate('/');
            return;
        }

        setIsConnectingGmail(true);
        try {
            const { auth_url } = await gmailService.getAuthUrl();
            // Redirect to Google OAuth page
            window.location.href = auth_url;
        } catch (error) {
            console.error('Failed to get Gmail auth URL:', error);
            if (error.response?.status === 401) {
                addToast('You must be logged in to connect Gmail account', 'error');
                navigate('/');
                return;
            }
            addToast(error.response?.data?.error?.message || 'Failed to initiate Gmail connection', 'error');
            setIsConnectingGmail(false);
        }
    };

    const handleDisconnectGmail = async () => {
        // Ensure user is authenticated before disconnecting Gmail
        if (!isAuthenticated || !user) {
            addToast('You must be logged in to disconnect Gmail account', 'error');
            navigate('/');
            return;
        }

        if (!window.confirm("Are you sure you want to disconnect your Gmail account? You will stop receiving email sync updates.")) {
            return;
        }

        setIsDisconnectingGmail(true);
        try {
            await gmailService.disconnect();
            addToast("Gmail account disconnected successfully", "success");
            await fetchGmailStatus();
        } catch (error) {
            console.error('Failed to disconnect Gmail:', error);
            if (error.response?.status === 401) {
                addToast('You must be logged in to disconnect Gmail account', 'error');
                navigate('/');
                return;
            }
            addToast(error.response?.data?.error?.message || 'Failed to disconnect Gmail account', 'error');
        } finally {
            setIsDisconnectingGmail(false);
        }
    };

    const handleSave = () => {
        localStorage.setItem('ghostedThreshold', ghostedThreshold);
        addToast("Preferences saved successfully", "success");
    };

    return (
        <div className="max-w-3xl mx-auto space-y-8 pb-12 relative">
            {isSyncing && (
                <SyncProgress 
                    onComplete={() => {
                        setIsSyncing(false);
                        fetchGmailStatus(); // Refresh Gmail status after sync
                    }} 
                    onClose={() => setIsSyncing(false)} 
                />
            )}
            <div className="flex justify-between items-start">
                <div>
                    <h1 className="text-3xl font-bold text-text-primary tracking-tight">Settings</h1>
                    <p className="mt-1 text-sm text-text-secondary">System configuration and preferences</p>
                </div>
                {user && (
                    <NeoBadge className="text-sm px-3 py-1">
                        <Shield className="h-3 w-3 mr-1" /> Role: {user.role || 'viewer'}
                    </NeoBadge>
                )}
            </div>

            {/* Account & Security */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <UserIcon className="h-5 w-5 mr-2 text-text-muted" />
                        Account Information
                    </h3>
                </div>
                <div className="p-6 space-y-6">
                    {user ? (
                        <div className="space-y-4 animate-fadeIn">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center">
                                    <div className="h-10 w-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-bold mr-4 shadow-neo-pressed border border-white/40 dark:border-white/5">
                                        {(user.full_name || user.email)?.charAt(0).toUpperCase() || 'U'}
                                    </div>
                                    <div>
                                        <p className="text-sm font-bold text-text-primary">
                                            {user.full_name || 'Logged in as'}
                                        </p>
                                        <p className="text-sm text-text-secondary">{user.email}</p>
                                    </div>
                                </div>
                                <NeoBadge variant={user.role === 'editor' ? 'success' : 'default'}>
                                    {user.role || 'viewer'}
                                </NeoBadge>
                            </div>
                            <div className="pt-4 border-t border-white/20 dark:border-white/5">
                                <NeoButton
                                    variant="danger"
                                    onClick={async () => {
                                        setIsLoggingOut(true);
                                        try {
                                            await logout();
                                            navigate('/');
                                        } catch (error) {
                                            console.error('Logout error:', error);
                                        } finally {
                                            setIsLoggingOut(false);
                                        }
                                    }}
                                    loading={isLoggingOut}
                                    disabled={isLoggingOut}
                                    className="w-full flex justify-center items-center"
                                    icon={LogOut}
                                >
                                    Sign Out
                                </NeoButton>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-4 animate-fadeIn">
                            <p className="text-text-secondary mb-4">Not logged in.</p>
                            <NeoButton onClick={() => navigate('/')}>
                                Go to Login
                            </NeoButton>
                        </div>
                    )}

                </div>
            </NeoCard>

            {/* Gmail Connection - Only show if user is authenticated */}
            {isAuthenticated && user && (
                <NeoCard className="p-0 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                        <h3 className="text-lg font-bold text-text-primary flex items-center">
                            <Mail className="h-5 w-5 mr-2 text-text-muted" />
                            Gmail Connection
                        </h3>
                    </div>
                    <div className="p-6 space-y-6">
                        {isLoadingGmailStatus ? (
                            <div className="text-center py-4 text-text-secondary">Checking Gmail connection status...</div>
                        ) : gmailStatus.is_connected ? (
                        <div className="space-y-4 animate-fadeIn">
                            <div className="flex items-center justify-between p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl border border-emerald-100/50 dark:border-emerald-800/30">
                                <div className="flex items-center">
                                    <CheckCircle className="h-5 w-5 text-emerald-500 dark:text-emerald-400 mr-3" />
                                    <div>
                                        <p className="text-sm font-bold text-emerald-800 dark:text-emerald-300">Gmail Connected</p>
                                        <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1">
                                            {gmailStatus.gmail_email || 'Connected to Gmail'}
                                        </p>
                                        {gmailStatus.connected_at && (
                                            <p className="text-xs text-emerald-600 dark:text-emerald-500 mt-1">
                                                Connected on {new Date(gmailStatus.connected_at).toLocaleDateString()}
                                            </p>
                                        )}
                                    </div>
                                </div>
                                <NeoBadge variant="success">Active</NeoBadge>
                            </div>
                            <div className="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-4 border border-amber-100/50 dark:border-amber-800/30 shadow-sm">
                                <div className="flex">
                                    <AlertTriangle className="h-5 w-5 text-amber-500 dark:text-amber-400 mt-0.5" />
                                    <div className="ml-3 flex-1">
                                        <h3 className="text-sm font-bold text-amber-800 dark:text-amber-300">Permission Scope: Read-Only</h3>
                                        <div className="mt-2 text-sm text-amber-700 dark:text-amber-400">
                                            <p>
                                                JobPulse AI only has access to view email subjects and snippets.
                                                We cannot delete, send, or modify your emails.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Token Scopes Information */}
                            {tokenScopes && (
                                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 border border-blue-100/50 dark:border-blue-800/30 shadow-sm">
                                    <div className="flex items-start">
                                        <Shield className="h-5 w-5 text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                                        <div className="ml-3 flex-1">
                                            <h3 className="text-sm font-bold text-blue-800 dark:text-blue-300 mb-2">
                                                Token Scopes (Debug Info)
                                            </h3>
                                            <div className="space-y-2 text-xs">
                                                <div>
                                                    <span className="font-semibold text-blue-700 dark:text-blue-400">Stored Scopes:</span>
                                                    <div className="mt-1 bg-white dark:bg-black/20 p-2 rounded border border-blue-200 dark:border-blue-700">
                                                        {tokenScopes.stored_scopes && tokenScopes.stored_scopes.length > 0 ? (
                                                            <ul className="list-disc list-inside space-y-1">
                                                                {tokenScopes.stored_scopes.map((scope, idx) => (
                                                                    <li key={idx} className="text-blue-900 dark:text-blue-300 font-mono text-xs break-all">
                                                                        {scope}
                                                                    </li>
                                                                ))}
                                                            </ul>
                                                        ) : (
                                                            <span className="text-blue-600 dark:text-blue-400">No scopes stored</span>
                                                        )}
                                                    </div>
                                                </div>
                                                <div>
                                                    <span className="font-semibold text-blue-700 dark:text-blue-400">Actual Token Scopes (from Google):</span>
                                                    <div className="mt-1 bg-white dark:bg-black/20 p-2 rounded border border-blue-200 dark:border-blue-700">
                                                        {tokenScopes.tokeninfo_scopes && tokenScopes.tokeninfo_scopes.length > 0 ? (
                                                            <ul className="list-disc list-inside space-y-1">
                                                                {tokenScopes.tokeninfo_scopes.map((scope, idx) => (
                                                                    <li key={idx} className="text-blue-900 dark:text-blue-300 font-mono text-xs break-all">
                                                                        {scope}
                                                                        {scope.includes('gmail.readonly') && (
                                                                            <span className="ml-2 text-green-600 dark:text-green-400">✓</span>
                                                                        )}
                                                                        {scope.includes('gmail.metadata') && (
                                                                            <span className="ml-2 text-red-600 dark:text-red-400">⚠</span>
                                                                        )}
                                                                    </li>
                                                                ))}
                                                            </ul>
                                                        ) : (
                                                            <span className="text-blue-600 dark:text-blue-400">Unable to verify</span>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4 pt-2 border-t border-blue-200 dark:border-blue-700">
                                                    <div className="flex items-center">
                                                        <span className={`h-2 w-2 rounded-full mr-2 ${tokenScopes.has_readonly ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                                        <span className="font-semibold text-blue-700 dark:text-blue-400">
                                                            Readonly: {tokenScopes.has_readonly ? '✓ Present' : '✗ Missing'}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center">
                                                        <span className={`h-2 w-2 rounded-full mr-2 ${tokenScopes.has_metadata ? 'bg-amber-500' : 'bg-gray-300'}`}></span>
                                                        <span className="font-semibold text-blue-700 dark:text-blue-400">
                                                            Metadata: {tokenScopes.has_metadata ? '⚠ Present' : '✓ Not Present'}
                                                        </span>
                                                    </div>
                                                </div>
                                                {tokenScopes.has_metadata && tokenScopes.has_readonly && (
                                                    <div className="pt-2 bg-amber-50 dark:bg-amber-900/30 rounded-lg p-3 border border-amber-200 dark:border-amber-800">
                                                        <p className="font-semibold text-amber-800 dark:text-amber-300 mb-1">
                                                            ⚠️ Warning: Token has BOTH readonly and metadata scopes
                                                        </p>
                                                        <p className="text-sm text-amber-700 dark:text-amber-400">
                                                            When both scopes are present, Google's API uses metadata scope restrictions, 
                                                            which do NOT support search queries (q parameter). This will cause 403 errors during sync. 
                                                            <strong className="block mt-1">Please disconnect and reconnect to get ONLY readonly scope.</strong>
                                                        </p>
                                                    </div>
                                                )}
                                                {tokenScopes.has_metadata && !tokenScopes.has_readonly && (
                                                    <div className="pt-2 bg-red-50 dark:bg-red-900/30 rounded-lg p-3 border border-red-200 dark:border-red-800">
                                                        <p className="font-semibold text-red-800 dark:text-red-300 mb-1">
                                                            ❌ Error: Token has ONLY metadata scope (readonly is missing)
                                                        </p>
                                                        <p className="text-sm text-red-700 dark:text-red-400">
                                                            Metadata scope does NOT support search queries. 
                                                            <strong className="block mt-1">Please disconnect and reconnect to get readonly scope.</strong>
                                                        </p>
                                                    </div>
                                                )}
                                                {!tokenScopes.has_metadata && !tokenScopes.has_readonly && (
                                                    <div className="pt-2 bg-red-50 dark:bg-red-900/30 rounded-lg p-3 border border-red-200 dark:border-red-800">
                                                        <p className="font-semibold text-red-800 dark:text-red-300 mb-1">
                                                            ❌ Error: No Gmail scopes found
                                                        </p>
                                                        <p className="text-sm text-red-700 dark:text-red-400">
                                                            Gmail connection is missing required scopes.
                                                            <strong className="block mt-1">Please disconnect and reconnect.</strong>
                                                        </p>
                                                    </div>
                                                )}
                                                {!tokenScopes.has_metadata && tokenScopes.has_readonly && (
                                                    <div className="pt-2 bg-green-50 dark:bg-green-900/30 rounded-lg p-3 border border-green-200 dark:border-green-800">
                                                        <p className="font-semibold text-green-800 dark:text-green-300 mb-1">
                                                            ✅ Perfect: Token has ONLY readonly scope
                                                        </p>
                                                        <p className="text-sm text-green-700 dark:text-green-400">
                                                            Your Gmail connection has the correct scope configuration. Email sync with search queries will work correctly.
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                            
                            {isLoadingScopes && (
                                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 border border-blue-100/50 dark:border-blue-800/30">
                                    <p className="text-sm text-blue-700 dark:text-blue-400 text-center">Loading token scope information...</p>
                                </div>
                            )}
                            <div className="pt-2 space-y-3">
                                <NeoButton
                                    onClick={() => setIsSyncing(true)}
                                    disabled={isSyncing}
                                    className="w-full flex justify-center items-center"
                                >
                                    <RefreshCw className="h-4 w-4 mr-2" />
                                    {isSyncing ? 'Syncing...' : 'Sync Emails Now'}
                                </NeoButton>
                                <NeoButton
                                    variant="danger"
                                    onClick={handleDisconnectGmail}
                                    loading={isDisconnectingGmail}
                                    disabled={isDisconnectingGmail}
                                    className="w-full flex justify-center items-center"
                                >
                                    <X className="h-4 w-4 mr-2" />
                                    Disconnect Gmail
                                </NeoButton>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-6 space-y-4 animate-fadeIn">
                            <div className="bg-slate-100 dark:bg-white/5 p-6 rounded-xl">
                                <Mail className="h-12 w-12 text-text-muted mx-auto mb-4" />
                                <h3 className="text-lg font-bold text-text-primary mb-2">Connect Your Gmail Account</h3>
                                <p className="text-sm text-text-secondary mb-6 max-w-md mx-auto">
                                    Connect your Gmail account to automatically track job application emails. 
                                    We use read-only access to scan for application-related emails.
                                </p>
                                <NeoButton
                                    onClick={handleConnectGmail}
                                    loading={isConnectingGmail}
                                    disabled={isConnectingGmail}
                                    className="px-8 py-3"
                                >
                                    <Mail className="h-4 w-4 mr-2" />
                                    {isConnectingGmail ? 'Connecting...' : 'Connect with Google'}
                                </NeoButton>
                            </div>
                            
                            {/* Redirect URI Configuration Info */}
                            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 border border-blue-100/50 dark:border-blue-800/30 mt-4">
                                <div className="flex items-start">
                                    <AlertTriangle className="h-5 w-5 text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                                    <div className="ml-3 flex-1">
                                        <h3 className="text-sm font-bold text-blue-800 dark:text-blue-300 mb-2">OAuth Redirect URI Configuration</h3>
                                        {isLoadingRedirectUri ? (
                                            <p className="text-xs text-blue-700 dark:text-blue-400">Loading redirect URI...</p>
                                        ) : redirectUri ? (
                                            <div className="space-y-2">
                                                <p className="text-xs text-blue-700 dark:text-blue-400">
                                                    Current redirect URI configured:
                                                </p>
                                                <div className="bg-white dark:bg-black/20 p-2 rounded border border-blue-200 dark:border-blue-700">
                                                    <code className="text-xs text-blue-900 dark:text-blue-300 break-all font-mono">
                                                        {redirectUri}
                                                    </code>
                                                </div>
                                                <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
                                                    ⚠️ Make sure this exact URI is registered in Google Cloud Console under "Authorized redirect URIs"
                                                </p>
                                            </div>
                                        ) : (
                                            <p className="text-xs text-blue-700 dark:text-blue-400">
                                                Unable to load redirect URI configuration. Make sure API Gateway is running with ENV=dev.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                        )}
                    </div>
                </NeoCard>
            )}

            {/* Theme & Appearance */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Monitor className="h-5 w-5 mr-2 text-text-muted" />
                        Appearance
                    </h3>
                </div>
                <div className="p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-bold text-text-primary">Theme Mode</p>
                            <p className="text-xs text-text-secondary mt-1">
                                Currently using <span className="font-semibold capitalize">{theme}</span> mode
                            </p>
                        </div>
                        <div className="flex items-center bg-app dark:bg-black/20 p-1.5 rounded-xl border border-white/50 dark:border-white/5">
                            <button
                                onClick={() => theme === 'dark' && toggleTheme()}
                                className={`p-2 rounded-lg transition-all flex items-center space-x-2 ${theme === 'light' ? 'bg-surface shadow-sm text-indigo-600' : 'text-text-muted hover:text-text-secondary'}`}
                            >
                                <Sun className="h-4 w-4" />
                                <span className="text-xs font-medium">Light</span>
                            </button>
                            <button
                                onClick={() => theme === 'light' && toggleTheme()}
                                className={`p-2 rounded-lg transition-all flex items-center space-x-2 ${theme === 'dark' ? 'bg-indigo-500/10 shadow-sm text-indigo-400' : 'text-text-muted hover:text-text-secondary'}`}
                            >
                                <Moon className="h-4 w-4" />
                                <span className="text-xs font-medium">Dark</span>
                            </button>
                        </div>
                    </div>
                </div>
            </NeoCard>

            {/* Application Logic */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Monitor className="h-5 w-5 mr-2 text-text-muted" />
                        Preferences
                    </h3>
                </div>
                <div className="p-6 space-y-6">
                    <div className="max-w-xs">
                        <label htmlFor="ghosted" className="block text-sm font-medium text-text-primary mb-2">
                            Ghosted Threshold (Days)
                        </label>
                        <p className="text-xs text-text-secondary mb-3">Auto-mark as 'Ghosted' if no contact after this many days.</p>
                        <div className="flex items-center">
                            <NeoInput
                                type="number"
                                id="ghosted"
                                value={ghostedThreshold}
                                onChange={(e) => setGhostedThreshold(e.target.value)}
                            />
                        </div>
                    </div>
                </div>
                <div className="px-6 py-4 bg-slate-100/50 dark:bg-white/5 text-right border-t border-gray-200/50 dark:border-white/5">
                    <NeoButton
                        onClick={handleSave}
                        className="inline-flex items-center"
                    >
                        <Save className="h-4 w-4 mr-2" />
                        Save Preferences
                    </NeoButton>
                </div>
            </NeoCard>

            {/* System Health */}
            <NeoCard className="p-0 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200/50 dark:border-white/5 bg-slate-100 dark:bg-white/5 flex items-center justify-between">
                    <h3 className="text-lg font-bold text-text-primary flex items-center">
                        <Server className="h-5 w-5 mr-2 text-text-muted" />
                        Backend Connection Status
                    </h3>
                    <NeoButton
                        variant="ghost"
                        size="sm"
                        onClick={fetchHealth}
                        disabled={isCheckingHealth}
                        className="text-xs"
                    >
                        <RefreshCw className={`h-3 w-3 mr-1 ${isCheckingHealth ? 'animate-spin' : ''}`} />
                        Refresh
                    </NeoButton>
                </div>
                <div className="p-6 space-y-4">
                    {/* API Gateway */}
                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm animate-pulse ${health.gateway ? 'bg-green-500' : health.gateway === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">API Gateway</p>
                                <p className="text-xs text-text-secondary">Main entry point (Port 8000)</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.gateway ? 'success' : health.gateway === false ? 'default' : 'default'}>
                            {health.gateway ? '✅ Connected' : health.gateway === false ? '❌ Offline' : '⏳ Checking...'}
                        </NeoBadge>
                    </div>

                    {/* Auth Service */}
                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm ${health.authService ? 'bg-green-500' : health.authService === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">Auth Service</p>
                                <p className="text-xs text-text-secondary">Authentication & authorization (Port 8003)</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.authService ? 'success' : health.authService === false ? 'default' : 'default'}>
                            {health.authService ? '✅ Connected' : health.authService === false ? '❌ Offline' : '⏳ Checking...'}
                        </NeoBadge>
                    </div>

                    {/* Application Service */}
                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm ${health.appService ? 'bg-green-500' : health.appService === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">Application Service</p>
                                <p className="text-xs text-text-secondary">Main backend API (Port 8002)</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.appService ? 'success' : health.appService === false ? 'default' : 'default'}>
                            {health.appService ? '✅ Connected' : health.appService === false ? '❌ Offline' : '⏳ Checking...'}
                        </NeoBadge>
                    </div>

                    {/* Email AI Service */}
                    <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-white/5 rounded-xl shadow-neo-pressed border border-transparent dark:border-white/5">
                        <div className="flex items-center">
                            <div className={`h-3 w-3 rounded-full mr-3 shadow-sm ${health.emailService ? 'bg-green-500' : health.emailService === false ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                            <div>
                                <p className="text-sm font-bold text-text-primary">Email AI Service</p>
                                <p className="text-xs text-text-secondary">Processing and sync engine (Port 8001)</p>
                            </div>
                        </div>
                        <NeoBadge variant={health.emailService ? 'success' : health.emailService === false ? 'default' : 'default'}>
                            {health.emailService ? '✅ Connected' : health.emailService === false ? '❌ Offline' : '⏳ Checking...'}
                        </NeoBadge>
                    </div>

                    {/* Overall Status */}
                    <div className={`mt-4 p-4 rounded-xl border-2 ${
                        health.gateway && health.authService 
                            ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' 
                            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                    }`}>
                        <p className="text-sm font-bold text-text-primary mb-1">
                            Overall Status: {health.gateway && health.authService ? '✅ Backend Connected' : '❌ Backend Offline'}
                        </p>
                        <p className="text-xs text-text-secondary">
                            {health.gateway && health.authService 
                                ? 'All critical services are operational. You can use authentication and API features.'
                                : 'Backend services are unavailable. Some features may not work. Please ensure backend services are running.'}
                        </p>
                    </div>
                </div>
            </NeoCard>

            <div className="text-center text-xs text-text-muted mt-8 mb-4">
                <p>JobPulse AI v1.0.0 (Beta)</p>
                <p>Environment: {import.meta.env.MODE || 'Development'}</p>
            </div>
        </div>
    );
}
