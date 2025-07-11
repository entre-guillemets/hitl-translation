// src/types/index.ts
export interface QualityPredictionData {
    sourceLanguage: string;
    targetLanguage: string;
    fileName: string;
    metrics: {
      bleuScore: number;
      cometScore: number;
      terScore: number;
      floresScore: number;
    };
    confidence: number;
    estimatedAccuracy: number;
  }
  
  export interface TranslationRequest {
    id: string;
    sourceLanguage: string;
    targetLanguages: string[];
    fileName: string;
    fileContent: string;
    status: 'pending' | 'quality-predicted' | 'completed' | 'reviewed';
    qualityPredictions?: QualityPredictionData[];
    createdAt: Date;
  }
  