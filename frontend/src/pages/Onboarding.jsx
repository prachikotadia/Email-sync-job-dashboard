import React, { useState } from 'react';
import { OnboardingWizard } from './OnboardingWizard';
import { useNavigate } from 'react-router-dom';

export default function OnboardingPage() {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-app flex items-center justify-center p-4">
            <div className="w-full max-w-4xl">
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-text-primary tracking-tight mb-2">Welcome to JobPulse.ai</h1>
                    <p className="text-lg text-text-secondary">Your AI-powered job search assistant.</p>
                </div>
                <OnboardingWizard onComplete={() => navigate('/dashboard')} />
            </div>
        </div>
    );
}
