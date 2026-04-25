import axios from 'axios';
import type { QualityPredictionData as QualityPrediction, TranslationRequest } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001';

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

// ── Persona CRUD ──────────────────────────────────────────────────────────────

export interface PersonaCreate {
  advertiserProfileId: string;
  name: string;
  psychographicDescription: string;
  messagingPriorities?: string[];
  toneOverride?: string | null;
  registerOverride?: string | null;
}

export interface PersonaUpdate {
  name?: string;
  psychographicDescription?: string;
  messagingPriorities?: string[];
  toneOverride?: string | null;
  registerOverride?: string | null;
}

export interface Persona {
  id: string;
  advertiserProfileId: string;
  name: string;
  psychographicDescription: string;
  messagingPriorities: string[];
  toneOverride: string | null;
  registerOverride: string | null;
  createdAt: string;
  updatedAt: string;
}

export const personaCrudService = {
  list: async (advertiserProfileId: string): Promise<Persona[]> => {
    const response = await apiClient.get('/api/personas', {
      params: { advertiserProfileId },
    });
    return response.data.personas;
  },

  create: async (data: PersonaCreate): Promise<Persona> => {
    const response = await apiClient.post('/api/personas', data);
    return response.data;
  },

  update: async (id: string, data: PersonaUpdate): Promise<Persona> => {
    const response = await apiClient.patch(`/api/personas/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/personas/${id}`);
  },
};

// ── Persona Transcreation ─────────────────────────────────────────────────────

export interface PersonaRunRequest {
  translationStringId: string;
  personaIds: string[];
  targetLanguage: string;
}

export interface PersonaTranscreationResult {
  rowId: string;
  personaId: string;
  personaName: string | null;
  psychographicDescription: string | null;
  outputText: string | null;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'NEEDS_REVIEW' | 'FAILED';
  brandVoiceScore: number | null;
  culturalFitnessScore: number | null;
  differentiationScore: number | null;
  tabooViolation: boolean | null;
  keyTermMissing: boolean | null;
  refinementAttempts: number;
  agentIterations: unknown[];
}

export interface PersonaComparisonResponse {
  translationStringId: string;
  sourceText: string;
  advertiserProfile: unknown;
  personas: PersonaTranscreationResult[];
}

export const personaTranscreationService = {
  /**
   * Run persona fan-out and return an EventSource for SSE consumption.
   * The caller is responsible for closing the EventSource.
   *
   * Usage:
   *   const es = personaTranscreationService.run(body);
   *   es.onmessage = (e) => { const event = JSON.parse(e.data); ... };
   *   es.onerror = () => es.close();
   */
  run: (body: PersonaRunRequest): EventSource => {
    const params = new URLSearchParams({
      translationStringId: body.translationStringId,
      targetLanguage: body.targetLanguage,
    });
    body.personaIds.forEach(id => params.append('personaIds', id));
    // SSE via POST is sent as a fetch; wrap in a minimal EventSource-like object
    // using a POST body since EventSource only supports GET. We use fetch + ReadableStream.
    // Return an object compatible with event consumption in the component.
    throw new Error(
      'Use personaTranscreationService.runStream() for SSE — EventSource does not support POST bodies.'
    );
  },

  /**
   * POST-based SSE stream for persona fan-out.
   * Returns a ReadableStreamDefaultReader that yields raw SSE lines.
   */
  runStream: async (
    body: PersonaRunRequest,
    onEvent: (event: Record<string, unknown>) => void,
    onDone: () => void,
    onError: (err: Error) => void,
  ): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/persona-transcreation/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok || !response.body) {
      onError(new Error(`HTTP ${response.status}: ${response.statusText}`));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() ?? '';

        for (const chunk of lines) {
          const line = chunk.trim();
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6));
              onEvent(parsed);
              if (parsed.type === 'done') onDone();
            } catch {
              // malformed SSE line — skip
            }
          }
        }
      }
    } catch (err) {
      onError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      reader.releaseLock();
    }
  },

  getResults: async (translationStringId: string) => {
    const response = await apiClient.get(`/api/persona-transcreation/${translationStringId}`);
    return response.data;
  },

  getComparison: async (translationStringId: string): Promise<PersonaComparisonResponse> => {
    const response = await apiClient.get(`/api/persona-transcreation/comparison/${translationStringId}`);
    return response.data;
  },

  approve: async (personaTranscreationId: string, domain = 'advertising'): Promise<void> => {
    await apiClient.post(`/api/persona-transcreation/${personaTranscreationId}/approve`, { domain });
  },
};

export default apiClient;
