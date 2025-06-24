"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { MultiSelect } from '@/components/ui/multi-select';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import React, { useMemo, useState } from 'react';

const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JP' },
  { label: 'French', value: 'FR' },
];

const API_BASE_URL = 'http://localhost:8001';

// Define available models for each language pair - IDs MUST match backend CleanMultiEngineService engine_configs keys
const LANGUAGE_PAIR_MODELS = {
  'EN-JP': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    // If ELAN_EN_JP model is not available, remove elan_quality from here for EN-JP
    // { id: 'elan_quality', label: 'ELAN Quality', description: 'Japanese specialist model' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
  ],
  'JP-EN': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Japanese specialist model' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
  ],
  'EN-FR': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Quality-focused model' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
  ],
  'FR-EN': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Quality-focused model' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
  ],
  'JP-FR': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'JP→EN→FR pivot via OPUS' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'JP→EN→FR pivot via ELAN' }, // This relies on pivot working
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model (direct if supported)' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model (direct if supported)' },
  ]
};

export const RequestTranslation: React.FC = () => {
  const [sourceLanguage, setSourceLanguage] = useState<string>('');
  const [targetLanguages, setTargetLanguages] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [wordCount, setWordCount] = useState<number>(0);
  const [isProcessingFile, setIsProcessingFile] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  
  const [useMultiEngine, setUseMultiEngine] = useState(false);
  const [selectedEngines, setSelectedEngines] = useState<string[]>([]);

  // Get available models based on current language pair selection
  const availableModels = useMemo(() => {
    if (!sourceLanguage || targetLanguages.length === 0) return [];
    
    // Get models for all selected language pairs
    const allModels: Array<{id: string, label: string, icon?: string, description: string, pairs: string[]}> = [];
    
    targetLanguages.forEach(target => {
      const pair = `${sourceLanguage}-${target}`;
      const pairModels = LANGUAGE_PAIR_MODELS[pair as keyof typeof LANGUAGE_PAIR_MODELS] || [];
      
      pairModels.forEach(model => {
        // Check if this model is already added
        const existingModel = allModels.find(m => m.id === model.id);
        if (existingModel) {
          // Add this pair to the existing model
          existingModel.pairs.push(pair);
        } else {
          // Add new model
          allModels.push({
            ...model,
            pairs: [pair]
          });
        }
      });
    });
    
    return allModels;
  }, [sourceLanguage, targetLanguages]);

  // Auto-select default models when language pair changes
  React.useEffect(() => {
    if (availableModels.length > 0 && selectedEngines.length === 0) {
      // Auto-select all available models
      const defaultSelection = availableModels.map(m => m.id);
      setSelectedEngines(defaultSelection);
    }
  }, [availableModels]);

  const countWords = (text: string, sourceLanguage?: string): number => {
    const isJapanese = sourceLanguage === 'JP' || /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]/.test(text);
    
    if (isJapanese) {
      const cleanText = text.replace(/[\s.,!?。！？、]/g, '');
      return cleanText.length;
    }
    
    const words = text.trim().split(/\s+/).filter(word => word.length > 0);
    return words.length;
  };

  const extractTextFromFile = async (file: File): Promise<string> => {
    const fileType = file.type;
    
    if (fileType === 'text/plain') {
      const text = await file.text();
      return text.normalize('NFC');
    } else if (fileType === 'application/pdf') {
      return 'PDF text extraction would require additional library (pdf-parse or similar)';
    } else if (fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
      return 'DOCX text extraction would require additional library (mammoth or similar)';
    } else {
      try {
        const text = await file.text();
        return text.normalize('NFC');
      } catch (error) {
        throw new Error('Unsupported file type for text extraction');
      }
    }
  };

  const getModelAndLanguagePair = (source: string, target: string) => {
    const pair = `${source}-${target}`;
    
    // Updated to match the backend model naming convention for single-engine requests
    const modelMapping: Record<string, string> = {
      'EN-FR': 'HELSINKI_EN_FR',
      'FR-EN': 'HELSINKI_FR_EN',
      'EN-JP': 'HELSINKI_EN_JP', // Default single model for EN-JP
      'JP-EN': 'OPUS_JA_EN',
      'JP-FR': 'PIVOT_ELAN_HELSINKI', // Defaulting to pivot for single engine JP-FR
    };
    
    // Fallback to the first available model for the pair, if multi-engine is not used.
    const defaultMtModel = LANGUAGE_PAIR_MODELS[pair as keyof typeof LANGUAGE_PAIR_MODELS]?.[0]?.id || 'HELSINKI_EN_FR';

    return {
      languagePair: pair,
      mtModel: modelMapping[pair] || defaultMtModel 
    };
  };

  const validateLanguagePair = (source: string, targets: string[]) => {
    const supportedPairs = Object.keys(LANGUAGE_PAIR_MODELS);
    return targets.every(target => supportedPairs.includes(`${source}-${target}`));
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = event.target.files?.[0];
    if (uploadedFile) {
      setFile(uploadedFile);
      setIsProcessingFile(true);
      setWordCount(0);
      setSubmitStatus('idle');

      try {
        const textContent = await extractTextFromFile(uploadedFile);
        const count = countWords(textContent, sourceLanguage);
        setWordCount(count);
      } catch (error) {
        console.error('Error processing file:', error);
        setWordCount(0);
      } finally {
        setIsProcessingFile(false);
      }
    }
  };

  const handleTargetLanguageChange = (newTargets: string[]) => {
    if (sourceLanguage) {
      const validTargets = newTargets.filter(target => 
        validateLanguagePair(sourceLanguage, [target])
      );
      setTargetLanguages(validTargets);
    } else {
      setTargetLanguages(newTargets);
    }
    // Reset selected engines when target languages change
    setSelectedEngines([]);
  };

  const handleSourceLanguageChange = (newSource: string) => {
    setSourceLanguage(newSource);
    if (file) {
      handleFileUpload({ target: { files: [file] } } as any);
    }
    if (targetLanguages.length > 0) {
      const validTargets = targetLanguages.filter(target => 
        validateLanguagePair(newSource, [target])
      );
      setTargetLanguages(validTargets);
    }
    // Reset selected engines when source language changes
    setSelectedEngines([]);
  };

  const handleEngineChange = (engine: string, checked: boolean) => {
    if (checked) {
      setSelectedEngines(prev => [...prev, engine]);
    } else {
      setSelectedEngines(prev => prev.filter(e => e !== engine));
    }
  };

  const handleSubmit = async () => {
    if (!sourceLanguage || targetLanguages.length === 0 || !file) return;
    
    setIsSubmitting(true);
    setSubmitStatus('idle');
    
    try {
      const textContent = await extractTextFromFile(file);
      
      let sentences;
      if (sourceLanguage === 'JP') {
        sentences = textContent.split(/[。！？]+/).filter(s => s.trim().length > 0);
      } else {
        sentences = textContent.split(/[.!?]+/).filter(s => s.trim().length > 0);
      }
      
      const endpoint = useMultiEngine         
        ? `${API_BASE_URL}/api/translation-requests/multi-engine`
        : `${API_BASE_URL}/api/translation-requests`;
      
      let requestData;
              
      if (useMultiEngine) {
        // Send selectedEngines directly, as their IDs now match backend engine_configs keys
        requestData = {
          sourceLanguage: sourceLanguage,
          targetLanguages: targetLanguages,
          languagePair: `${sourceLanguage}-${targetLanguages.join(',')}`,
          wordCount,
          fileName: file.name,
          sourceTexts: sentences,
          engines: selectedEngines
        };
      } else {
        const { languagePair, mtModel } = getModelAndLanguagePair(sourceLanguage, targetLanguages[0]);
        requestData = {
          sourceLanguage: sourceLanguage,
          targetLanguages: targetLanguages,
          languagePair,
          mtModel,
          wordCount,
          fileName: file.name,
          sourceTexts: sentences
        };
      }
      
      console.log('Submitting request data:', requestData);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Server error:', errorText);
        throw new Error(`Failed to submit translation request: ${errorText}`);
      }
      
      const result = await response.json();
      setSubmitStatus('success');
      
      console.log('Translation request created:', result);
      
      setTimeout(() => {
        setSourceLanguage('');
        setTargetLanguages([]);
        setFile(null);
        setWordCount(0);
        setSubmitStatus('idle');
        setUseMultiEngine(false);
        setSelectedEngines([]);
      }, 2000);
      
    } catch (error) {
      console.error('Error submitting translation request:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getAvailableTargetLanguages = () => {
    if (!sourceLanguage) return languageOptions;
    
    return languageOptions.filter(lang => {
      if (lang.value === sourceLanguage) return false;
      return validateLanguagePair(sourceLanguage, [lang.value]);
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Request Translation</h1>
      </div>

      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Create New Translation Request</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Source Language
              </label>
              <Select value={sourceLanguage} onValueChange={handleSourceLanguageChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source language" />
                </SelectTrigger>
                <SelectContent>
                  {languageOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Target Languages
              </label>
              <MultiSelect
                options={getAvailableTargetLanguages()}
                selectedValues={targetLanguages}
                onSelectionChange={handleTargetLanguageChange}
                placeholder="Select target languages"
              />
              {sourceLanguage && targetLanguages.length === 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Available pairs: {getAvailableTargetLanguages().map(l => l.label).join(', ')}
                </p>
              )}
            </div>
          </div>

          {/* Show available models when language pair is selected */}
          {sourceLanguage && targetLanguages.length > 0 && (
            <div className="space-y-4 p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="multiEngine"
                  checked={useMultiEngine}
                  onCheckedChange={(checked) => setUseMultiEngine(checked as boolean)}
                />
                <label htmlFor="multiEngine" className="text-sm font-medium">
                  Use Multi-Model Translation
                </label>
                <Badge variant="outline" className="text-xs">
                  Compare {availableModels.length} Available Models
                </Badge>
              </div>
              
              {useMultiEngine && availableModels.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Available models for {targetLanguages.map(t => `${sourceLanguage}→${t}`).join(', ')}:
                  </p>
                  <div className="space-y-3">
                    {availableModels.map((model) => (
                      <div key={model.id} className="flex items-start space-x-3 p-3 border rounded-md hover:bg-muted/50 transition-colors">
                        <Checkbox
                          id={model.id}
                          checked={selectedEngines.includes(model.id)}
                          onCheckedChange={(checked) => handleEngineChange(model.id, checked as boolean)}
                          className="mt-1"
                        />
                        <div className="flex-1">
                          <label htmlFor={model.id} className="text-sm font-medium flex items-center gap-2 cursor-pointer">
                            <span>{model.icon}</span>
                            {model.label}
                          </label>
                          <p className="text-xs text-muted-foreground mt-1">
                            {model.description}
                          </p>
                          <p className="text-xs text-blue-600 mt-1">
                            Supports: {model.pairs.join(', ')}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {selectedEngines.length === 0 && (
                    <p className="text-xs text-red-600">
                      Please select at least one translation model.
                    </p>
                  )}
                </div>
              )}

              {!useMultiEngine && availableModels.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  Single model mode will use: {availableModels[0]?.label}
                </div>
              )}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium mb-2">Upload File</label>
            <input
              type="file"
              onChange={handleFileUpload}
              accept=".txt,.pdf,.docx,.doc"
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            {file && (
              <div className="mt-2 text-sm text-gray-600">
                <p><strong>Selected:</strong> {file.name}</p>
                <p><strong>Size:</strong> {formatFileSize(file.size)}</p>
                {isProcessingFile && (
                  <p className="text-blue-600">Processing file...</p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium mb-2">Translation Summary</h3>
              <div className="text-sm text-gray-600 space-y-1">
                <p><strong>Source:</strong> {sourceLanguage ? languageOptions.find(l => l.value === sourceLanguage)?.label : 'Not selected'}</p>
                <p><strong>Targets:</strong> {targetLanguages.length > 0 ? targetLanguages.map(lang => languageOptions.find(l => l.value === lang)?.label).join(', ') : 'None selected'}</p>
                <p><strong>File:</strong> {file?.name || 'No file selected'}</p>
                {useMultiEngine && selectedEngines.length > 0 && (
                  <p><strong>Models:</strong> 
                    <span className="ml-1 text-purple-600">
                      {selectedEngines.map(engine => availableModels.find(m => m.id === engine)?.label).join(', ')}
                    </span>
                  </p>
                )}
                {file && (
                  <p><strong>Word Count:</strong> 
                    {isProcessingFile ? (
                      <span className="text-blue-600 ml-1">Calculating...</span>
                    ) : (
                      <span className="ml-1 font-semibold text-green-600">
                        {wordCount.toLocaleString()} {sourceLanguage === 'JP' ? 'characters' : 'words'}
                      </span>
                    )}
                  </p>
                )}
                {file && wordCount > 0 && targetLanguages.length > 0 && (
                  <p><strong>Total {sourceLanguage === 'JP' ? 'Characters' : 'Words'} to Translate:</strong> 
                    <span className="ml-1 font-semibold text-blue-600">
                      {(wordCount * targetLanguages.length * (useMultiEngine ? selectedEngines.length : 1)).toLocaleString()} {sourceLanguage === 'JP' ? 'characters' : 'words'}
                    </span>
                  </p>
                )}
                {sourceLanguage && targetLanguages.length > 0 && (
                  <p><strong>Language Pairs:</strong> 
                    <span className="ml-1 text-purple-600">
                      {targetLanguages.map(target => `${sourceLanguage}-${target}`).join(', ')}
                    </span>
                  </p>
                )}
              </div>
            </div>
          </div>

          {submitStatus === 'success' && (
            <div className="p-3 bg-green-100 border border-green-400 text-green-700 rounded">
              Translation request submitted successfully! Form will reset shortly.
            </div>
          )}

          {submitStatus === 'error' && (
            <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              Failed to submit translation request. Please try again.
            </div>
          )}

          <Button 
            className="w-full" 
            onClick={handleSubmit}
            disabled={
              !sourceLanguage || 
              targetLanguages.length === 0 || 
              !file || 
              isProcessingFile || 
              isSubmitting ||
              (useMultiEngine && selectedEngines.length === 0)
            }
          >
            {isSubmitting ? 'Submitting...' : 
             useMultiEngine ? `Submit Multi-Model Translation (${selectedEngines.length} models)` :
             'Submit Translation Request'}
          </Button>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>WMT Benchmark Testing</CardTitle>
              <p className="text-sm text-muted-foreground">
                Test with professional WMT datasets for standardized evaluation using local models
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { pair: "jpn-eng", label: "JP→EN" },
                  { pair: "eng-jpn", label: "EN→JP" },
                  { pair: "eng-fra", label: "EN→FR" },
                  { pair: "fra-eng", label: "FR→EN" },
                  { pair: "jpn-fra", label: "JP→FR (Pivot)" }
                ].map(({ pair, label }) => (
                  <Button 
                    key={pair}
                    variant="outline"
                    onClick={async () => {
                      try {
                        const response = await fetch(`${API_BASE_URL}/api/wmt/create-request?language_pair=${pair}&sample_size=10`, {
                          method: 'POST'
                        });
                        if (response.ok) {
                          alert(`WMT ${label} test created!`);
                        } else {
                          const error = await response.text();
                          alert(`Failed to create ${label} test: ${error}`);
                        }
                      } catch (error) {
                        console.error('Failed to create WMT request:', error);
                        alert(`Error creating ${label} test`);
                      }
                    }}
                  >
                    Test {label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  );
};

export default RequestTranslation;