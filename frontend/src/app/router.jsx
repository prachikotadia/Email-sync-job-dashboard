import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from '../pages/Login';
import Dashboard from '../pages/Dashboard';
import Applications from '../pages/Applications';
import Resumes from '../pages/Resumes';
import Export from '../pages/Export';
import Settings from '../pages/Settings';
import OnboardingPage from '../pages/Onboarding';
import { Layout } from './layout/Layout';
import { RequireAuth } from './guards/RequireAuth';

export function AppRouter() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Login />} />
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
