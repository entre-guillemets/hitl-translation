// src/services/qualityService.ts

export interface CometScoreRequest {
    source: string;
    hypothesis: string;
    reference: string;
  }
  
  export interface CometScoreResponse {
    score: number;
    system_score: number;
    model: string;
    score_range: string;
    reference_based: boolean;
  }
  
  export interface BatchCometRequest {
    translations: Array<{
      id?: string | number;
      source: string;
      hypothesis: string;
      reference: string;
    }>;
  }
  
  export interface BatchCometResponse {
    results: Array<{
      translation_id: string | number;
      score: number;
      source: string;
      hypothesis: string;
      reference: string;
    }>;
    system_score: number;
    total_translations: number;
    model: string;
  }
  
  export interface QualityMetricsRequest {
    requestId: string;
  }
  
  export interface QualityMetricsResponse {
    request_id: string;
    total_strings: number;
    metrics: Array<{
      string_id: string;
      source_text: string;
      translated_text: string;
      target_language: string;
      comet_score: number | null;
      human_rating: number | null;
      has_annotations: boolean;
      processing_time_ms: number;
    }>;
    averages: {
      comet_score: number | null;
      human_rating: number | null;
      processing_time_ms: number;
    };
  }
  
  export class QualityService {
    private baseUrl: string;
  
    constructor(baseUrl: string = 'http://localhost:8001') {
      this.baseUrl = baseUrl;
    }
  
    async calculateCometScore(request: CometScoreRequest): Promise<CometScoreResponse> {
      const response = await fetch(`${this.baseUrl}/api/quality-assessment/comet-score`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });
  
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`COMET scoring failed: ${errorData.detail || response.statusText}`);
      }
  
      return response.json();
    }
  
    async calculateBatchCometScores(request: BatchCometRequest): Promise<BatchCometResponse> {
      const response = await fetch(`${this.baseUrl}/api/quality-assessment/batch-comet-score`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });
  
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Batch COMET scoring failed: ${errorData.detail || response.statusText}`);
      }
  
      return response.json();
    }
  
    async calculateQualityMetrics(requestId: string): Promise<QualityMetricsResponse> {
      const response = await fetch(`${this.baseUrl}/api/quality-assessment/calculate-metrics`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requestId }),
      });
  
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Quality metrics calculation failed: ${errorData.detail || response.statusText}`);
      }
  
      return response.json();
    }
  
    async getQualitySummary(requestId: string) {
      const response = await fetch(`${this.baseUrl}/api/quality-assessment/quality-summary/${requestId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
  
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Quality summary failed: ${errorData.detail || response.statusText}`);
      }
  
      return response.json();
    }
  
    async getQualityTrends() {
      const response = await fetch(`${this.baseUrl}/api/quality-assessment/analytics/quality-trends`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
  
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Quality trends failed: ${errorData.detail || response.statusText}`);
      }
  
      return response.json();
    }
  
    // Health check method
    async checkConnection(): Promise<boolean> {
      try {
        const response = await fetch(`${this.baseUrl}/`, {
          method: 'GET',
        });
        return response.ok;
      } catch (error) {
        return false;
      }
    }
  }
  
  // Export singleton instance
  export const qualityService = new QualityService(
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001'
  );
  