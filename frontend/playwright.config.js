import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './tests',
    timeout: 30000,
    expect: {
        timeout: 5000
    },
    use: {
        baseURL: 'http://localhost:5174',
        trace: 'on-first-retry',
        viewport: { width: 1280, height: 720 }
    },
    webServer: {
        command: 'npm run dev',
        port: 5174,
        reuseExistingServer: !process.env.CI
    }
});
