import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Login from '../pages/Login';
import Dashboard from '../pages/Dashboard';
import Applications from '../pages/Applications';
import Resumes from '../pages/Resumes';
import Export from '../pages/Export';
import Settings from '../pages/Settings';
import OnboardingPage from '../pages/Onboarding';
import { Layout } from './layout/Layout';
import { RequireAuth } from './guards/RequireAuth';
import { useAuth } from '../context/AuthContext';

// Redirect authenticated users away from login page
function LoginRedirect({ children }) {
    const { isAuthenticated, isLoading } = useAuth();
    const location = useLocation();

    if (isLoading) {
        return (
            <div className="min-h-screen bg-app flex items-center justify-center">
                <div className="text-text-secondary">Loading...</div>
            </div>
        );
    }

    if (isAuthenticated) {
        // Redirect to the page they were trying to access, or dashboard
        const from = location.state?.from?.pathname || '/dashboard';
        return <Navigate to={from} replace />;
    }

    return children;
}

export function AppRouter() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={
                    <LoginRedirect>
                        <Login />
                    </LoginRedirect>
                } />
                <Route path="/onboarding" element={<RequireAuth><OnboardingPage /></RequireAuth>} />
                <Route element={<RequireAuth><Layout /></RequireAuth>}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/applications" element={<Applications />} />
                    <Route path="/applications/:id" element={<Applications />} />
                    <Route path="/resumes" element={<Resumes />} />
                    <Route path="/export" element={<Export />} />
                    <Route path="/settings" element={<Settings />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    );
}
