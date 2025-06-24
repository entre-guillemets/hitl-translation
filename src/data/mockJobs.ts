// src/data/mockJobs.ts
export interface TranslationJob {
  id: string;
  submissionDate: string;
  submissionTime: string;
  sourceLanguage: string;
  targetLanguages: string[];
  fileName: string;
  status: 'pending' | 'completed' | 'in-progress';
  metrics?: {
    bleu: number;
    comet: number;
    ter: number;
    metricX: {
      score: number;        // 0-25 scale (lower is better)
      confidence: number;   // Model confidence
      mode: 'reference-based' | 'reference-free';
      variant: 'MetricX-24-Hybrid' | 'MetricX-24-XL' | 'MetricX-24-XXL';
    };
  };
}

export interface Annotation {
  id: string;
  category: 'grammar' | 'word-choice' | 'context' | 'other';
  severity: 'low' | 'medium' | 'high';
  comment: string;
  reviewer?: string;
  timestamp: string;
  textRange?: { start: number; end: number };
}

export interface TranslationString {
  id: string;
  jobId: string;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  status: 'draft' | 'reviewed' | 'finalized';
  annotations: Annotation[];
  isApproved: boolean;
  fuzzyMatch?: {
    percentage: number;
    matchedText: string;
    source: 'translation-memory' | 'glossary' | 'previous-job';
  };
  metricXScore?: {
    score: number;
    confidence: number;
    mode: 'reference-based' | 'reference-free';
  };
}

// Command Center Reference Data Interfaces
export interface TranslationMemory {
  id: string;
  sourceText: string;
  targetText: string;
  sourceLanguage: string;
  targetLanguage: string;
  quality: 'high' | 'medium' | 'low';
  domain: string;
  lastUsed: string;
}

export interface GlossaryTerm {
  id: string;
  term: string;
  translation: string;
  sourceLanguage: string;
  targetLanguage: string;
  domain: string;
  definition?: string;
  notes?: string;
}

export interface DoNotTranslateItem {
  id: string;
  text: string;
  category: 'brand' | 'proper-noun' | 'technical' | 'other';
  languages: string[];
  notes?: string;
}

export interface OffensiveWord {
  id: string;
  word: string;
  language: string;
  severity: 'low' | 'medium' | 'high';
  category: 'profanity' | 'hate-speech' | 'discriminatory' | 'other';
  alternatives?: string[];
}

export const mockTranslationJobs: TranslationJob[] = [
  {
    id: '1',
    submissionDate: '2025-06-01',
    submissionTime: '14:30:00',
    sourceLanguage: 'en',
    targetLanguages: ['es', 'fr'],
    fileName: 'document1.pdf',
    status: 'completed',
    metrics: {
      bleu: 0.85,
      comet: 0.78,
      ter: 0.15,
      metricX: {
        score: 8.2,
        confidence: 0.92,
        mode: 'reference-based',
        variant: 'MetricX-24-Hybrid'
      }
    }
  },
  {
    id: '2',
    submissionDate: '2025-06-01',
    submissionTime: '10:15:00',
    sourceLanguage: 'fr',
    targetLanguages: ['en', 'de', 'it'],
    fileName: 'report.docx',
    status: 'completed',
    metrics: {
      bleu: 0.82,
      comet: 0.75,
      ter: 0.18,
      metricX: {
        score: 12.1,
        confidence: 0.88,
        mode: 'reference-based',
        variant: 'MetricX-24-Hybrid'
      }
    }
  },
  {
    id: '3',
    submissionDate: '2025-05-31',
    submissionTime: '16:45:00',
    sourceLanguage: 'de',
    targetLanguages: ['en'],
    fileName: 'manual.txt',
    status: 'in-progress'
  },
  {
    id: '4',
    submissionDate: '2025-05-30',
    submissionTime: '09:20:00',
    sourceLanguage: 'es',
    targetLanguages: ['en', 'pt'],
    fileName: 'article.pdf',
    status: 'completed',
    metrics: {
      bleu: 0.88,
      comet: 0.82,
      ter: 0.12,
      metricX: {
        score: 6.8,
        confidence: 0.95,
        mode: 'reference-based',
        variant: 'MetricX-24-Hybrid'
      }
    }
  },
  {
    id: '5',
    submissionDate: '2025-05-29',
    submissionTime: '13:10:00',
    sourceLanguage: 'en',
    targetLanguages: ['zh', 'ja', 'ko'],
    fileName: 'presentation.pptx',
    status: 'pending'
  }
];

export const mockTranslationStrings: TranslationString[] = [
  {
    id: '1',
    jobId: '1',
    sourceText: 'Welcome to our translation management system.',
    translatedText: 'Bienvenido a nuestro sistema de gestión de traducciones.',
    targetLanguage: 'es',
    status: 'draft',
    annotations: [],
    isApproved: false,
    fuzzyMatch: {
      percentage: 95,
      matchedText: 'Welcome to our platform',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 7.2,
      confidence: 0.91,
      mode: 'reference-based'
    }
  },
  {
    id: '2',
    jobId: '1',
    sourceText: 'Please review the document carefully.',
    translatedText: 'Por favor, revise el documento cuidadosamente.',
    targetLanguage: 'es',
    status: 'reviewed',
    annotations: [
      {
        id: 'a1',
        category: 'word-choice',
        severity: 'medium',
        comment: 'Consider using "con atención" instead of "cuidadosamente"',
        reviewer: 'John Doe',
        timestamp: '2025-06-02T10:30:00Z'
      }
    ],
    isApproved: false,
    fuzzyMatch: {
      percentage: 87,
      matchedText: 'Please review the document',
      source: 'previous-job'
    },
    metricXScore: {
      score: 9.8,
      confidence: 0.85,
      mode: 'reference-based'
    }
  },
  {
    id: '3',
    jobId: '1',
    sourceText: 'The quality metrics look excellent.',
    translatedText: 'Les métriques de qualité semblent excellentes.',
    targetLanguage: 'fr',
    status: 'finalized',
    annotations: [],
    isApproved: true,
    fuzzyMatch: {
      percentage: 100,
      matchedText: 'The quality metrics look excellent.',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 5.1,
      confidence: 0.97,
      mode: 'reference-based'
    }
  },
  {
    id: '4',
    jobId: '1',
    sourceText: 'This system provides comprehensive translation analysis.',
    translatedText: 'Les métriques de qualité paraissent excellentes.',
    targetLanguage: 'fr',
    status: 'reviewed',
    annotations: [
      {
        id: 'a2',
        category: 'context',
        severity: 'high',
        comment: 'Translation does not match the source text meaning. Should be about "system" and "analysis".',
        reviewer: 'Marie Dubois',
        timestamp: '2025-06-02T11:15:00Z'
      }
    ],
    isApproved: false,
    fuzzyMatch: {
      percentage: 45,
      matchedText: 'The quality metrics',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 18.7,
      confidence: 0.93,
      mode: 'reference-based'
    }
  },
  {
    id: '5',
    jobId: '2',
    sourceText: 'Machine translation has improved significantly.',
    translatedText: 'Die maschinelle Übersetzung hat sich erheblich verbessert.',
    targetLanguage: 'de',
    status: 'draft',
    annotations: [],
    isApproved: false,
    fuzzyMatch: {
      percentage: 92,
      matchedText: 'Machine translation has improved',
      source: 'previous-job'
    },
    metricXScore: {
      score: 6.9,
      confidence: 0.89,
      mode: 'reference-based'
    }
  },
  {
    id: '6',
    jobId: '2',
    sourceText: 'Neural networks enable better language understanding.',
    translatedText: 'Neuronale Netzwerke ermöglichen ein besseres Sprachverständnis.',
    targetLanguage: 'de',
    status: 'finalized',
    annotations: [],
    isApproved: true,
    fuzzyMatch: {
      percentage: 78,
      matchedText: 'Neural networks enable better understanding',
      source: 'glossary'
    },
    metricXScore: {
      score: 7.8,
      confidence: 0.92,
      mode: 'reference-based'
    }
  },
  {
    id: '7',
    jobId: '2',
    sourceText: 'The BLEU score indicates translation quality.',
    translatedText: 'Der BLEU-Score zeigt die Übersetzungsqualität an.',
    targetLanguage: 'de',
    status: 'reviewed',
    annotations: [
      {
        id: 'a3',
        category: 'grammar',
        severity: 'low',
        comment: 'Consider using "gibt an" instead of "zeigt an" for better flow.',
        reviewer: 'Hans Mueller',
        timestamp: '2025-06-02T09:45:00Z'
      }
    ],
    isApproved: false,
    fuzzyMatch: {
      percentage: 89,
      matchedText: 'The BLEU score indicates quality',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 8.5,
      confidence: 0.87,
      mode: 'reference-based'
    }
  },
  {
    id: '8',
    jobId: '4',
    sourceText: 'Artificial intelligence transforms language processing.',
    translatedText: 'La inteligencia artificial transforma el procesamiento del lenguaje.',
    targetLanguage: 'es',
    status: 'draft',
    annotations: [],
    isApproved: false,
    fuzzyMatch: {
      percentage: 83,
      matchedText: 'Artificial intelligence transforms processing',
      source: 'glossary'
    },
    metricXScore: {
      score: 7.1,
      confidence: 0.90,
      mode: 'reference-based'
    }
  },
  {
    id: '9',
    jobId: '4',
    sourceText: 'Quality assurance ensures accurate translations.',
    translatedText: 'O controle de qualidade garante traduções precisas.',
    targetLanguage: 'pt',
    status: 'reviewed',
    annotations: [
      {
        id: 'a4',
        category: 'word-choice',
        severity: 'medium',
        comment: 'Consider "asseguramento de qualidade" for a more literal translation of "quality assurance".',
        reviewer: 'Carlos Silva',
        timestamp: '2025-06-02T14:20:00Z'
      }
    ],
    isApproved: false,
    fuzzyMatch: {
      percentage: 91,
      matchedText: 'Quality assurance ensures accurate',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 9.2,
      confidence: 0.86,
      mode: 'reference-based'
    }
  },
  {
    id: '10',
    jobId: '4',
    sourceText: 'Human reviewers provide valuable feedback.',
    translatedText: 'Los revisores humanos proporcionan comentarios valiosos.',
    targetLanguage: 'es',
    status: 'finalized',
    annotations: [],
    isApproved: true,
    fuzzyMatch: {
      percentage: 96,
      matchedText: 'Human reviewers provide valuable feedback',
      source: 'previous-job'
    },
    metricXScore: {
      score: 5.8,
      confidence: 0.94,
      mode: 'reference-based'
    }
  },
  {
    id: '11',
    jobId: '1',
    sourceText: 'Advanced machine learning algorithms optimize results.',
    translatedText: 'Les algorithmes d\'apprentissage automatique avancés optimisent les résultats.',
    targetLanguage: 'fr',
    status: 'draft',
    annotations: [],
    isApproved: false,
    fuzzyMatch: {
      percentage: 72,
      matchedText: 'Machine learning algorithms optimize',
      source: 'glossary'
    },
    metricXScore: {
      score: 8.9,
      confidence: 0.88,
      mode: 'reference-based'
    }
  },
  {
    id: '12',
    jobId: '2',
    sourceText: 'Real-time translation processing capabilities.',
    translatedText: 'Echtzeit-Übersetzungsverarbeitungsfähigkeiten.',
    targetLanguage: 'de',
    status: 'reviewed',
    annotations: [],
    isApproved: false,
    fuzzyMatch: {
      percentage: 65,
      matchedText: 'Real-time processing capabilities',
      source: 'translation-memory'
    },
    metricXScore: {
      score: 11.3,
      confidence: 0.82,
      mode: 'reference-based'
    }
  }
];

// Command Center Reference Data
export const mockTranslationMemories: TranslationMemory[] = [
  {
    id: '1',
    sourceText: 'Welcome to our platform',
    targetText: 'Bienvenido a nuestra plataforma',
    sourceLanguage: 'en',
    targetLanguage: 'es',
    quality: 'high',
    domain: 'general',
    lastUsed: '2025-06-01'
  },
  {
    id: '2',
    sourceText: 'Machine learning model',
    targetText: 'Modèle d\'apprentissage automatique',
    sourceLanguage: 'en',
    targetLanguage: 'fr',
    quality: 'high',
    domain: 'technology',
    lastUsed: '2025-05-30'
  },
  {
    id: '3',
    sourceText: 'Quality assurance process',
    targetText: 'Qualitätssicherungsprozess',
    sourceLanguage: 'en',
    targetLanguage: 'de',
    quality: 'medium',
    domain: 'business',
    lastUsed: '2025-05-28'
  },
  {
    id: '4',
    sourceText: 'Neural network architecture',
    targetText: 'Architettura di rete neurale',
    sourceLanguage: 'en',
    targetLanguage: 'it',
    quality: 'high',
    domain: 'technology',
    lastUsed: '2025-05-25'
  },
  {
    id: '5',
    sourceText: 'Translation memory database',
    targetText: 'Base de dados de memória de tradução',
    sourceLanguage: 'en',
    targetLanguage: 'pt',
    quality: 'medium',
    domain: 'technology',
    lastUsed: '2025-05-20'
  }
];

export const mockGlossaryTerms: GlossaryTerm[] = [
  {
    id: '1',
    term: 'API',
    translation: 'API',
    sourceLanguage: 'en',
    targetLanguage: 'es',
    domain: 'technology',
    definition: 'Application Programming Interface',
    notes: 'Keep as API in Spanish'
  },
  {
    id: '2',
    term: 'Dashboard',
    translation: 'Tableau de bord',
    sourceLanguage: 'en',
    targetLanguage: 'fr',
    domain: 'technology',
    definition: 'Control panel interface'
  },
  {
    id: '3',
    term: 'BLEU Score',
    translation: 'BLEU-Bewertung',
    sourceLanguage: 'en',
    targetLanguage: 'de',
    domain: 'machine-translation',
    definition: 'Bilingual Evaluation Understudy metric'
  },
  {
    id: '4',
    term: 'Neural Network',
    translation: 'Rete Neurale',
    sourceLanguage: 'en',
    targetLanguage: 'it',
    domain: 'artificial-intelligence',
    definition: 'Computing system inspired by biological neural networks'
  },
  {
    id: '5',
    term: 'Quality Assurance',
    translation: 'Garantia de Qualidade',
    sourceLanguage: 'en',
    targetLanguage: 'pt',
    domain: 'business',
    definition: 'Process of ensuring quality standards are met'
  }
];

export const mockDoNotTranslateItems: DoNotTranslateItem[] = [
  {
    id: '1',
    text: 'OpenAI',
    category: 'brand',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Company name - keep as is'
  },
  {
    id: '2',
    text: 'ChatGPT',
    category: 'brand',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Product name - do not translate'
  },
  {
    id: '3',
    text: 'JSON',
    category: 'technical',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Technical acronym'
  },
  {
    id: '4',
    text: 'GitHub',
    category: 'brand',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Platform name - preserve as is'
  },
  {
    id: '5',
    text: 'HTTP',
    category: 'technical',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Protocol acronym'
  },
  {
    id: '6',
    text: 'Microsoft',
    category: 'brand',
    languages: ['es', 'fr', 'de', 'it', 'pt'],
    notes: 'Company name'
  }
];

export const mockOffensiveWords: OffensiveWord[] = [
  {
    id: '1',
    word: 'hate',
    language: 'en',
    severity: 'medium',
    category: 'hate-speech',
    alternatives: ['dislike', 'disapprove']
  },
  {
    id: '2',
    word: 'stupid',
    language: 'en',
    severity: 'low',
    category: 'discriminatory',
    alternatives: ['unwise', 'incorrect']
  },
  {
    id: '3',
    word: 'odio',
    language: 'es',
    severity: 'medium',
    category: 'hate-speech',
    alternatives: ['disgustar', 'desaprobar']
  },
  {
    id: '4',
    word: 'idiot',
    language: 'en',
    severity: 'medium',
    category: 'discriminatory',
    alternatives: ['mistaken', 'confused']
  },
  {
    id: '5',
    word: 'haine',
    language: 'fr',
    severity: 'medium',
    category: 'hate-speech',
    alternatives: ['déplaire', 'désapprouver']
  },
  {
    id: '6',
    word: 'Hass',
    language: 'de',
    severity: 'medium',
    category: 'hate-speech',
    alternatives: ['missbilligen', 'ablehnen']
  }
];
