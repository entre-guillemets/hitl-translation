// src/hooks/useTranslation.ts
import { useState } from 'react';
import { translationService } from '../services/api';
import { TranslationRequest } from '../types';

export const useTranslation = () => {
  const [translations, setTranslations] = useState<TranslationRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitTranslation = async (request: Partial<TranslationRequest>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await translationService.submitTranslationRequest(request);
      setTranslations(prev => [...prev, result]);
      return result;
    } catch (err) {
      setError('Failed to submit translation request');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    translations,
    loading,
    error,
    submitTranslation,
  };
};
