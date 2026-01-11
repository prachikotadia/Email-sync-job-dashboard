import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useDemoMode } from '../../hooks/useDemoMode';

export function RequireAuth({ children }) {
    const location = useLocation();
    const { isAuthenticated, isLoading } = useAuth();
    const { isDemoMode } = useDemoMode();

    // Show loading state while checking authentication
    if (isLoading) {
        return (
            <div className="min-h-screen bg-app flex items-center justify-center">
                <div className="text-text-secondary">Loading...</div>
            </div>
        );
    }

    // Allow access if authenticated (real auth) or in demo mode
    const canAccess = isAuthenticated || isDemoMode;

    if (!canAccess) {
        return <Navigate to="/" state={{ from: location }} replace />;
    }

    return children;
}
