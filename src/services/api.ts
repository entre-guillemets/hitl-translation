import axios from 'axios';
import { QualityPrediction, TranslationRequest } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout for model inference
});

// Add request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const translationService = {
  submitTranslationRequest: async (formData: FormData): Promise<TranslationRequest> => {
    const response = await apiClient.post('/translations/submit', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getQualityPrediction: async (requestId: string): Promise<QualityPrediction[]> => {
    const response = await apiClient.get(`/translations/${requestId}/quality-prediction`);
    return response.data;
  },

  // Enhanced mock function with MetricX-like scoring
  mockQualityPrediction: async (
    sourceLanguage: string, 
    targetLanguages: string[], 
    fileName: string
  ): Promise<QualityPrediction[]> => {
    // Simulate API delay for model inference
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    return targetLanguages.map(targetLang => {
      // Generate more realistic MetricX scores
      const metricxScore = Math.random() * 15 + 5; // 5-20 range
      
      return {
        sourceLanguage,
        targetLanguage: targetLang,
        fileName,
        metrics: {
          bleuScore: Math.random() * 0.3 + 0.7, // 0.7-1.0
          cometScore: Math.random() * 0.2 + 0.75, // 0.75-0.95
          terScore: Math.random() * 0.3 + 0.1, // 0.1-0.4 (lower is better)
          floresScore: Math.random() * 0.25 + 0.7, // 0.7-0.95
          metricxScore: metricxScore, // Add MetricX score
        },
        confidence: Math.random() * 0.2 + 0.8, // 0.8-1.0
        estimatedAccuracy: Math.random() * 0.15 + 0.85, // 0.85-1.0
        qualityLevel: getQualityLevelFromScore(metricxScore),
      };
    });
  },

  // Method for MetricX-specific endpoints
  evaluateWithMetricX: async (
    source: string,
    hypothesis: string,
    reference?: string,
    sourceLanguage: string = 'auto',
    targetLanguage: string = 'auto'
  ) => {
    const response = await apiClient.post('/api/metricx/evaluate', {
      source,
      hypothesis,
      reference,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    });
    return response.data;
  },
};

// Helper function to determine quality level from MetricX score
function getQualityLevelFromScore(score: number): 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' {
  if (score <= 7) return 'EXCELLENT';
  if (score <= 12) return 'GOOD';
  if (score <= 18) return 'FAIR';
  return 'POOR';
}

export default apiClient;
