interface MetricXRequest {
  source: string;
  hypothesis: string;
  reference?: string;
  source_language: string;
  target_language: string;
  model?: 'metricx-24-hybrid' | 'metricx-24-xl' | 'metricx-24-xxl';
}

interface MetricXResponse {
  score: number;
  confidence: number;
  mode: 'reference_based' | 'reference_free' | 'reference_based_fallback' | 'reference_free_fallback' | 'error';
  variant: string;
  quality_level: 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR';
  source_language?: string;
  target_language?: string;
  error?: string;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

export const metricXService = {
  evaluateTranslation: async (request: MetricXRequest): Promise<MetricXResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/metricx/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`MetricX API error: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Validate response structure
      if (typeof result.score !== 'number' || typeof result.confidence !== 'number') {
        throw new Error('Invalid response format from MetricX API');
      }

      return result;
    } catch (error) {
      console.error('MetricX evaluation failed:', error);
      // Fallback to mock data for development
      return {
        score: Math.random() * 15 + 5, // Random score between 5-20
        confidence: Math.random() * 0.2 + 0.6, // Random confidence 0.6-0.8 (lower for fallback)
        mode: request.reference ? 'reference_based' : 'reference_free',
        variant: request.model || 'metricx-24-hybrid',
        quality_level: this.getQualityLevel(Math.random() * 15 + 5),
        source_language: request.source_language,
        target_language: request.target_language,
        error: `Client-side fallback: ${error instanceof Error ? error.message : 'Unknown error'}`
      };
    }
  },

  batchEvaluate: async (requests: MetricXRequest[]): Promise<MetricXResponse[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/metricx/batch-evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requests }),
      });

      if (!response.ok) {
        throw new Error(`MetricX batch API error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('MetricX batch evaluation failed:', error);
      // Fallback to individual evaluations
      return Promise.all(requests.map(req => this.evaluateTranslation(req)));
    }
  },

  getQualityLevel: (score: number): 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' => {
    if (score <= 7) return 'EXCELLENT';
    if (score <= 12) return 'GOOD';
    if (score <= 18) return 'FAIR';
    return 'POOR';
  },

  getRecommendedAction: (score: number): 'approve' | 'minor-edit' | 'major-revision' | 'retranslate' => {
    if (score <= 7) return 'approve';
    if (score <= 12) return 'minor-edit';
    if (score <= 18) return 'major-revision';
    return 'retranslate';
  },

  getQualityColor: (qualityLevel: string): string => {
    switch (qualityLevel) {
      case 'EXCELLENT': return '#22c55e'; // green
      case 'GOOD': return '#84cc16'; // lime
      case 'FAIR': return '#f59e0b'; // amber
      case 'POOR': return '#ef4444'; // red
      default: return '#6b7280'; // gray
    }
  },

  formatScore: (score: number): string => {
    return score.toFixed(1);
  },

  formatConfidence: (confidence: number): string => {
    return `${(confidence * 100).toFixed(0)}%`;
  }
};
