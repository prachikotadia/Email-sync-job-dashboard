// Helper to manage URL query params state
export function getQueryParams(searchParams) {
    const params = {};
    for (const [key, value] of searchParams.entries()) {
        params[key] = value;
    }
    return params;
}

export function updateQueryParams(setSearchParams, newParams) {
    setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        Object.entries(newParams).forEach(([key, value]) => {
            if (value === undefined || value === null || value === '') {
                next.delete(key);
            } else {
                next.set(key, value);
            }
        });
        return next;
    });
}
