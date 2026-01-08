import { Navigate, useLocation } from 'react-router-dom';
import { useDemoMode } from '../../hooks/useDemoMode';

export function RequireAuth({ children }) {
    const location = useLocation();
    // For demo purposes, we assume 'authToken' exists if logged in, 
    // or just let it pass if we are in "Demo Mode".
    // MVP: Just check if we are not trying to access login while already logged in.

    const { isDemoMode } = useDemoMode();
    const isAuthenticated = isDemoMode || localStorage.getItem('authToken') !== null;

    if (!isAuthenticated) {
        return <Navigate to="/" state={{ from: location }} replace />;
    }

    return children;
}
