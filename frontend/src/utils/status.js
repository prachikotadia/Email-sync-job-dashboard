export const STATUS_LABELS = {
    'APPLIED': 'Applied',
    'INTERVIEW': 'Interview',
    'OFFER': 'Offer',
    'REJECTED': 'Rejected',
    'GHOSTED': 'Ghosted' // Computed status
};

export const STATUS_COLORS = {
    'Applied': 'default',
    'Interview': 'primary', // Indigo
    'Offer': 'success',     // Emerald
    'Rejected': 'danger',   // Red
    'Ghosted': 'default',   // Gray
    'Withdrawn': 'warning'
};

export const CONFIDENCE_THRESHOLDS = {
    HIGH: 0.8,
    MEDIUM: 0.6
};

// Helper to get color for confidence
export const getConfidenceColor = (score) => {
    if (!score && score !== 0) return 'text-gray-400';
    if (score >= CONFIDENCE_THRESHOLDS.HIGH) return 'text-emerald-500';
    if (score >= CONFIDENCE_THRESHOLDS.MEDIUM) return 'text-amber-500';
    return 'text-red-500';
};
