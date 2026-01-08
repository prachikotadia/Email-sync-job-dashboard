import { useEffect } from 'react';

export function useKeyboardShortcuts(shortcuts) {
    useEffect(() => {
        const handleKeyDown = (event) => {
            // Ignore if input/textarea is focused
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
                if (event.key === 'Escape') {
                    document.activeElement.blur();
                }
                return;
            }

            const key = event.key.toLowerCase();
            if (shortcuts[key]) {
                event.preventDefault();
                shortcuts[key](event);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [shortcuts]);
}
