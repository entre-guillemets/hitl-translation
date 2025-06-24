// src/config/api.ts
export const API_BASE_URL = 'http://localhost:8001';
export const API_ENDPOINTS = {
  TRANSLATION_REQUESTS: `${API_BASE_URL}/api/translation-requests`,
  QUALITY_METRICS_CALCULATE: `${API_BASE_URL}/api/quality-metrics/calculate`,
  HEALTH: `${API_BASE_URL}/api/health`,
};
