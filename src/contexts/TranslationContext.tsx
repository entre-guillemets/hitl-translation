// src/contexts/TranslationContext.tsx
import type { ReactNode } from 'react';
import React, { createContext, useContext, useState } from 'react';
import type { QualityPrediction, TranslationRequest } from '../types';

interface TranslationContextType {
  currentRequest: TranslationRequest | null;
  setCurrentRequest: (request: TranslationRequest | null) => void;
  qualityPredictions: QualityPrediction[];
  setQualityPredictions: (predictions: QualityPrediction[]) => void;
}

const TranslationContext = createContext<TranslationContextType | undefined>(undefined);

export const TranslationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentRequest, setCurrentRequest] = useState<TranslationRequest | null>(null);
  const [qualityPredictions, setQualityPredictions] = useState<QualityPrediction[]>([]);

  return (
    <TranslationContext.Provider value={{
      currentRequest,
      setCurrentRequest,
      qualityPredictions,
      setQualityPredictions,
    }}>
      {children}
    </TranslationContext.Provider>
  );
};

export const useTranslation = () => {
  const context = useContext(TranslationContext);
  if (context === undefined) {
    throw new Error('useTranslation must be used within a TranslationProvider');
  }
  return context;
};