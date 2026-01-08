import { test, expect } from '@playwright/test';

test.describe('Smoke Test - Demo Flow', () => {
    test('Login in Demo Mode and Navigate', async ({ page }) => {
        page.on('console', msg => console.log('PAGE LOG:', msg.text()));

        // 1. Visit Login
        await page.goto('/');
        await expect(page).toHaveTitle(/JobPulse AI/);

        // 2. Click Demo Mode
        const demoBtn = page.getByText('Continue (Demo Mode)');
        await demoBtn.click();

        // 3. Verify Dashboard
        await expect(page).toHaveURL(/.*\/dashboard/);
        await expect(page.getByText('JobPulse', { exact: true })).toBeVisible(); // Sidebar Title
        await expect(page.getByText('Dashboard Overview')).toBeVisible(); // Dashboard content

        // 3b. Test Theme Toggle
        const themeToggle = page.getByRole('button', { name: /Switch to dark mode/i });
        await expect(themeToggle).toBeVisible();
        await themeToggle.click();
        await expect(page.locator('html')).toHaveClass(/dark/);

        // Toggle back
        await page.getByRole('button', { name: /Switch to light mode/i }).click();
        await expect(page.locator('html')).not.toHaveClass(/dark/);

        // 4. Navigate to Applications
        await page.getByRole('link', { name: 'Applications' }).click();
        await expect(page).toHaveURL(/.*\/applications/);

        // Wait for table to load (skeleton gone)
        await expect(page.getByRole('table')).toBeVisible();
        await expect(page.getByText('Google')).toBeVisible(); // From mock seed

        // 5. Open Drawer
        await page.getByText('Google').click();
        await expect(page.getByText('Applying for')).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Senior Frontend Engineer' })).toBeVisible();

        // Close drawer (Esc or button)
        await page.keyboard.press('Escape');

        // 6. Navigate to Resumes
        await page.getByRole('link', { name: 'Resumes' }).click();
        await expect(page).toHaveURL(/.*\/resumes/);
        await expect(page.getByText('Resume_Frontend_2025.pdf')).toBeVisible();

        // 7. Navigate to Export
        await page.getByRole('link', { name: 'Export' }).click();
        await expect(page).toHaveURL(/.*\/export/);

        // 8. Logout
        // Open mobile menu if needed? No, purely desktop smoke usually fine. 
        // Sidebar "Sign Out" button
        await page.getByRole('button', { name: /Sign Out/i }).click();
        await expect(page).toHaveURL(/http:\/\/localhost:517./);
    });
});
