/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                app: 'var(--bg-app)', // Dynamic background
                surface: 'var(--bg-surface)', // Dynamic surface
                'text-primary': 'var(--text-primary)',
                'text-secondary': 'var(--text-secondary)',
                'text-muted': 'var(--text-muted)',
            },
            boxShadow: {
                'neo': 'var(--shadow-neo)',
                'neo-pressed': 'var(--shadow-neo-pressed)',
                'neo-input': 'var(--shadow-neo-input)',
                'neo-button': 'var(--shadow-neo-button)',
                'neo-button-active': 'var(--shadow-neo-button-active)',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { transform: 'translateY(10px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                slideInRight: {
                    '0%': { transform: 'translateX(20px)', opacity: '0' },
                    '100%': { transform: 'translateX(0)', opacity: '1' },
                },
                scaleIn: {
                    '0%': { transform: 'scale(0.95)', opacity: '0' },
                    '100%': { transform: 'scale(1)', opacity: '1' },
                }
            },
            animation: {
                fadeIn: 'fadeIn 0.5s ease-out',
                slideUp: 'slideUp 0.6s ease-out',
                slideInRight: 'slideInRight 0.5s ease-out',
                scaleIn: 'scaleIn 0.4s ease-out',
            }
        },
    },
    plugins: [],
}
