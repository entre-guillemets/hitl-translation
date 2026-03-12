// src/config/api.ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001';

export const API_ENDPOINTS = {
  TRANSLATION_REQUESTS: `${API_BASE_URL}/api/translation-requests`,
  MULTI_ENGINE: `${API_BASE_URL}/api/translation-requests/multi-engine`,
  TRIPLE_OUTPUT: `${API_BASE_URL}/api/translation-requests/triple-output`,
  FILE_SINGLE_ENGINE: `${API_BASE_URL}/api/translation-requests/file-single-engine`,
  FILE_MULTI_ENGINE: `${API_BASE_URL}/api/translation-requests/file-multi-engine`,
  FILE_PREPROCESSING: `${API_BASE_URL}/api/translation-requests/file-preprocessing`,
  DETECT_LANGUAGE: `${API_BASE_URL}/api/translation-requests/detect-language`,
  FUZZY_MATCHES: `${API_BASE_URL}/api/translation-requests/fuzzy-matches`,
  TRANSLATION_PREFERENCES: `${API_BASE_URL}/api/translation-requests/translation-preferences`,
  QUALITY_METRICS_CALCULATE: `${API_BASE_URL}/api/quality-metrics/calculate`,
  ANALYTICS: `${API_BASE_URL}/analytics`,
  HEALTH: `${API_BASE_URL}/api/health`,
  WMT_BENCHMARKS: `${API_BASE_URL}/api/wmt`,
  DEBUG: `${API_BASE_URL}/api/debug`,
};
