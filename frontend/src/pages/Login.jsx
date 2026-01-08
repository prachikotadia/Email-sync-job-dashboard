import React from 'react';
import { useNavigate } from 'react-router-dom';
import { NeoCard } from '../ui/NeoCard';
import { NeoButton } from '../ui/NeoButton';
import { useDemoMode } from '../hooks/useDemoMode';

export default function Login() {
    const navigate = useNavigate();

    const { enableDemoMode } = useDemoMode();

    const handleDemoLogin = () => {
        enableDemoMode();
        navigate('/dashboard');
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
                    <div className="space-y-6">
                        <div>
                            <NeoButton
                                onClick={handleDemoLogin}
                                className="w-full flex justify-center py-3 text-base"
                            >
                                Continue (Demo Mode)
                            </NeoButton>
                        </div>

                        <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-white/20 dark:border-white/5" />
                            </div>
                            <div className="relative flex justify-center text-sm">
                                <span className="px-3 bg-surface text-text-muted">Or continue with</span>
                            </div>
                        </div>

                        <div>
                            <NeoButton
                                variant="secondary"
                                disabled
                                className="w-full inline-flex justify-center items-center py-3 opacity-60 cursor-not-allowed"
                            >
                                <svg className="h-5 w-5 mr-2" aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .533 5.333.533 12S5.867 24 12.48 24c3.44 0 6.1-1.12 7.853-2.933 1.787-1.84 2.32-4.427 2.32-6.502 0-.64-.067-1.28-.187-1.889H12.48z" />
                                </svg>
                                Google (Coming Soon)
                            </NeoButton>
                        </div>
                    </div>
                </NeoCard>
            </div>
        </div>
    );
}
