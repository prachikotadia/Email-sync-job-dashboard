import { appClient } from './appClient';

export async function downloadExport(filters) {
    try {
        const response = await appClient.get('/export', {
            params: filters,
            responseType: 'blob'
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `export_${new Date().toISOString()}.xlsx`);
        document.body.appendChild(link);
        link.click();
        link.parentNode.removeChild(link);
        return true;
    } catch (e) {
        console.error("Export failed", e);
        throw e;
    }
}
