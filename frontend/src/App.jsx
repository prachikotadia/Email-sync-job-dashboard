import { ToastProvider } from './context/ToastContext';
import { AppRouter } from './app/router';

import { ThemeProvider } from './context/ThemeContext';
import { DemoProvider } from './context/DemoContext';

function App() {
  return (
    <ThemeProvider>
      <DemoProvider>
        <ToastProvider>
          <AppRouter />
        </ToastProvider>
      </DemoProvider>
    </ThemeProvider>
  );
}

export default App;
