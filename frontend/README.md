# JobPulse AI - Frontend

This is the frontend repository for **JobPulse AI**, an AI-powered Gmail Job Application Tracker.
It provides a SaaS-style dashboard to track, manage, and analyze your job applications synced from your email.

## 🚀 Tech Stack

- **Framework**: React (Vite)
- **Styling**: Tailwind CSS
- **Routing**: React Router DOM (v6)
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **Charts**: Recharts
- **Dates**: date-fns
- **Utils**: clsx, tailwind-merge

## 🛠️ Project Setup

1.  **Install dependencies**:
    ```bash
    npm install
    ```

2.  **Environment Variables**:
    The project uses `.env` for backend service URLs. A default is provided:
    ```env
    VITE_EMAIL_AI_BASE_URL=http://localhost:8001
    VITE_APP_BASE_URL=http://localhost:8002
    ```

3.  **Run Development Server**:
    ```bash
    npm run dev
    ```
    The app will start at `http://localhost:5173` (by default).

## 📱 Features

-   **Dashboard**: KPI cards, application status charts, and recent activity feed.
-   **Applications**: Filterable table view of all applications, with a slide-over detail drawer.
-   **Resumes**: Manage uploaded resumes and map them to applications.
-   **Export**: Download application data as Excel.
-   **Sync**: One-click synchronization with the backend services.

## 🎨 Theme System

The application supports both Light and Dark modes using Tailwind CSS variables.

-   **Theme Context**: Managed by `ThemeContext.jsx`, persisting user preference in `localStorage`.
-   **CSS Variables**: Defined in `index.css` (e.g., `--bg-app`, `--bg-surface`, `--text-primary`).
-   **Neo Design System**: All `Neo*` components consume theme tokens via `neoTheme.js`.

To toggle the theme, use the sun/moon icon in the top navigation bar or the "Appearance" card in Settings.

## 📂 Project Structure

```
src/
├── components/
│   ├── layout/       # Sidebar, Topbar, Layout wrapper
│   └── ui/           # Shared UI components (Badge, Button, etc.)
├── pages/            # Page components (Dashboard, Login, etc.)
├── services/         # API clients (Axios setup)
├── utils/            # Helper functions
├── types/            # Type definitions (if using TS/JSDoc)
├── hooks/            # Custom React hooks
├── App.jsx           # Main Router setup
└── main.jsx          # Entry point
```

## ⚠️ Notes

-   **Demo Mode**: Click "Continue (Demo Mode)" on the login screen to access the dashboard without authentication (MVP feature).
-   **Mock Data**: The frontend currently uses mock data for visual demonstration if the backend is not reachable.
