import { ToastProvider } from './context/ToastContext';
import { AppRouter } from './app/router';

import { ThemeProvider } from './context/ThemeContext';
import { DemoProvider } from './context/DemoContext';
import { AuthProvider } from './context/AuthContext';

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <DemoProvider>
            <AppRouter />
          </DemoProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;
