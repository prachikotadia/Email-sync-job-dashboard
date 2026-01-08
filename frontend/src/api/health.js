import { emailAiClient } from './emailAiClient';
import { appClient } from './appClient';

export async function checkHealth() {
    try {
        const [emailAi, app] = await Promise.allSettled([
            emailAiClient.get('/health'),
            appClient.get('/health')
        ]);

        return {
            emailAi: emailAi.status === 'fulfilled',
            app: app.status === 'fulfilled'
        };
    } catch (e) {
        return { emailAi: false, app: false };
    }
}
