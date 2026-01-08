export const MOCK_APPLICATIONS = [
    {
        id: '1',
        company: 'Google',
        role: 'Senior Frontend Engineer',
        status: 'INTERVIEW',
        appliedDate: '2025-05-15T10:00:00Z',
        lastUpdate: '2025-05-20T14:30:00Z',
        confidence: 0.92,
        aiReason: 'Received an email about scheduling a technical screen.',
        snippet: 'We would like to schedule a 45-minute technical interview...'
    },
    {
        id: '2',
        company: 'Amazon',
        role: 'SDE II',
        status: 'REJECTED',
        appliedDate: '2025-05-10T09:00:00Z',
        lastUpdate: '2025-05-12T11:00:00Z',
        confidence: 0.98,
        aiReason: 'Email subject "Update on your application" contained rejection keywords.',
        snippet: 'Thank you for your interest, but we have decided to move forward with other candidates.'
    },
    {
        id: '3',
        company: 'Netflix',
        role: 'UI Engineer',
        status: 'OFFER',
        appliedDate: '2025-05-01T10:00:00Z',
        lastUpdate: '2025-05-22T16:00:00Z',
        confidence: 0.99,
        aiReason: 'Email contained "Offer Letter" attachment and salary details.',
        snippet: 'We are pleased to offer you the position of UI Engineer...'
    },
    {
        id: '4',
        company: 'Startup Inc',
        role: 'Founding Engineer',
        status: 'APPLIED',
        appliedDate: '2025-05-24T08:00:00Z',
        lastUpdate: '2025-05-24T08:00:00Z',
        confidence: 0.65,
        aiReason: 'Confirmation of application receipt.',
        snippet: 'Thanks for applying! We will review your profile shortly.'
    },
    {
        id: '5',
        company: 'Meta',
        role: 'Product Designer',
        status: 'GHOSTED', // Inferred
        appliedDate: '2025-04-01T10:00:00Z',
        lastUpdate: '2025-04-01T10:00:00Z',
        confidence: 0.5,
        aiReason: 'No activity for > 30 days.',
        snippet: 'Application confirmation.'
    }
];

export const MOCK_METRICS = {
    total: 124,
    active: 45,
    interviewing: 12,
    offers: 3,
    ghosted: 15,
    rejected: 49,
    responseRate: 18.2
};

export const MOCK_ACTIVITY = [
    { id: 1, type: 'email', description: 'Received interview invite from Google', time: '2h ago', icon: 'Mail' },
    { id: 2, type: 'status', description: 'Amazon status changed to Rejected', time: '1d ago', icon: 'XCircle' },
    { id: 3, type: 'email', description: 'Netflix sent an offer letter!', time: '2d ago', icon: 'CheckCircle' }
];

export const MOCK_RESUMES = [
    { id: 1, name: 'Resume_Frontend_2025.pdf', tags: ['frontend', 'react'], uploadedAt: '2025-05-01' },
    { id: 2, name: 'Resume_FullStack_v2.pdf', tags: ['fullstack', 'node'], uploadedAt: '2025-04-20' }
];
