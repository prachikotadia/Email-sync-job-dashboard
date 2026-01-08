import React, { createContext, useContext, useState, useEffect } from 'react';

const DemoContext = createContext();

export const DEMO_KEY = 'jp_demo_mode';

export function DemoProvider({ children }) {
    const [isDemoMode, setIsDemoMode] = useState(() => {
        return localStorage.getItem(DEMO_KEY) === 'true';
    });

    useEffect(() => {
        const handleTrigger = () => {
            if (!isDemoMode) {
                console.log("Auto-switching to Demo Mode due to API failure");
                setIsDemoMode(true);
                localStorage.setItem(DEMO_KEY, 'true');
            }
        };
        window.addEventListener('demo-mode-trigger', handleTrigger);
        return () => window.removeEventListener('demo-mode-trigger', handleTrigger);
    }, [isDemoMode]);

    const enableDemoMode = () => {
        if (!isDemoMode) {
            console.log("Switching to Demo Mode");
            setIsDemoMode(true);
            localStorage.setItem(DEMO_KEY, 'true');
        }
    };

    const disableDemoMode = () => {
        setIsDemoMode(false);
        localStorage.setItem(DEMO_KEY, 'false');
    };

    return (
        <DemoContext.Provider value={{ isDemoMode, enableDemoMode, disableDemoMode }}>
            {children}
        </DemoContext.Provider>
    );
}

export function useDemoContext() {
    const context = useContext(DemoContext);
    if (!context) {
        throw new Error('useDemoContext must be used within a DemoProvider');
    }
    return context;
}
