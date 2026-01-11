// This file is now a wrapper that uses the centralized API client from services/api.js
// All requests go through the API Gateway with proper auth handling
export { apiClient as appClient } from '../services/api';
