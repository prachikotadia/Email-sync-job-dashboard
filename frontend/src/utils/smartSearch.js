export function smartSearch(items, query, fields = []) {
    if (!query) return items;
    const lowerQuery = query.toLowerCase();

    // Check for "status:rejected" type filters
    const statusMatch = lowerQuery.match(/status:([a-z]+)/);
    let activeStatusFilter = null;
    let cleanQuery = lowerQuery;

    if (statusMatch) {
        activeStatusFilter = statusMatch[1];
        cleanQuery = lowerQuery.replace(statusMatch[0], '').trim();
    }

    return items.filter(item => {
        // Apply status filter if present
        if (activeStatusFilter) {
            if (item.status && !item.status.toLowerCase().includes(activeStatusFilter)) {
                return false;
            }
        }

        // Apply text search
        if (!cleanQuery) return true;

        // Search in specified fields or all string values
        const searchAgainst = fields.length > 0
            ? fields.map(f => item[f])
            : Object.values(item);

        return searchAgainst.some(val =>
            String(val).toLowerCase().includes(cleanQuery)
        );
    });
}
