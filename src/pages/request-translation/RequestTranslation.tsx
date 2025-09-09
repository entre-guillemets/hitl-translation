"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { MultiSelect } from '@/components/ui/multi-select';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import React, { useEffect, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';

const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JA' },
  { label: 'French', value: 'FR' },
];

const API_BASE_URL = 'http://localhost:8001';

const LANGUAGE_PAIR_MODELS = {
  'EN-JA': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
  ],
  'JA-EN': [
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
  'JA-FR': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'JA→EN→FR pivot via OPUS' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'JA→EN→FR pivot via ELAN' },
    { id: 't5_versatile', label: 'mT5 Versatile', description: 'Multilingual T5 model (direct if supported)' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model (direct if supported)' },
  ],  
  'FR-JA': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'FR→EN→JA pivot via OPUS' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'FR→EN→JA pivot via ELAN' },
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
  const [isDetectingLanguage, setIsDetectingLanguage] = useState<boolean>(false);
  
  const [useMultiEngine, setUseMultiEngine] = useState(false);
  const [selectedEngines, setSelectedEngines] = useState<string[]>([]);

  const availableModels = useMemo(() => {
    if (!sourceLanguage || targetLanguages.length === 0) return [];
    
    const allModels: Array<{id: string, label: string, icon?: string, description: string, pairs: string[]}> = [];
    
    targetLanguages.forEach(target => {
      const pair = `${sourceLanguage}-${target}`;
      const pairModels = LANGUAGE_PAIR_MODELS[pair as keyof typeof LANGUAGE_PAIR_MODELS] || [];
      
      pairModels.forEach(model => {
        const existingModel = allModels.find(m => m.id === model.id);
        if (existingModel) {
          existingModel.pairs.push(pair);
        } else {
          allModels.push({
            ...model,
            pairs: [pair]
          });
        }
      });
    });
    
    return allModels;
  }, [sourceLanguage, targetLanguages]);

  useEffect(() => {
    if (availableModels.length > 0 && selectedEngines.length === 0) {
      const defaultSelection = availableModels.map(m => m.id);
      setSelectedEngines(defaultSelection);
    }
  }, [availableModels]);

  const countWords = (text: string, sourceLanguage?: string): number => {
    const isJapanese = sourceLanguage === 'JA' || /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]/.test(text);
    
    if (isJapanese) {
      const cleanText = text.replace(/[\s.,!?。！？、]/g, '');
      return cleanText.length;
    }
    
    const words = text.trim().split(/\s+/).filter(word => word.length > 0);
    return words.length;
  };

  const extractTextFromFile = async (file: File): Promise<string> => {
    const fileType = file.type;
    
    if (fileType.includes('text/plain')) {
      const text = await file.text();
      return text.normalize('NFC');
    } else {
      return 'Content from non-text file types will be extracted on the backend.';
    }
  };

  const getModelAndLanguagePair = (source: string, target: string) => {
    const pair = `${source}-${target}`;
    
    const modelMapping: Record<string, string> = {
      'EN-FR': 'HELSINKI_EN_FR',
      'FR-EN': 'HELSINKI_FR_EN',
      'EN-JA': 'HELSINKI_EN_JA',
      'JA-EN': 'OPUS_JA_EN',
      'JA-FR': 'PIVOT_ELAN_HELSINKI',
    };
    
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
  
  const handleFileUpload = async (event: { files: File[] }) => {
    const uploadedFile = event.files?.[0];
    if (!uploadedFile) return;

    setFile(uploadedFile);
    setWordCount(0);
    setSubmitStatus('idle');
    setSourceLanguage('');
    setIsDetectingLanguage(true);

    const formData = new FormData();
    formData.append('file', uploadedFile);

    try {
        const langResponse = await fetch(`${API_BASE_URL}/api/translation-requests/detect-language`, {
            method: 'POST',
            body: formData,
        });

        if (!langResponse.ok) throw new Error('Failed to detect language.');

        const langResult = await langResponse.json();
        const detectedLanguage = langResult.language;
        
        const supportedLang = languageOptions.find(l => l.value === detectedLanguage);

        if (supportedLang) {
            setSourceLanguage(supportedLang.value);
            const textContent = await extractTextFromFile(uploadedFile);
            setWordCount(countWords(textContent, supportedLang.value));
        } else {
            setSourceLanguage('');
            alert(`Detected language "${detectedLanguage}" is not supported. Please select the correct language manually.`);
        }

    } catch (error) {
        console.error('Error processing file:', error);
        alert(error instanceof Error ? error.message : "An unknown error occurred.");
        setSourceLanguage('');
    } finally {
        setIsDetectingLanguage(false);
    }
};

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => handleFileUpload({ files: acceptedFiles }),
    accept: {
      'text/plain': ['.txt'],
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx', '.doc'],
      'image/*': ['.jpg', '.jpeg', '.png', '.gif'],
      'audio/*': ['.mp3', '.wav', '.flac']
    },
    multiple: false
  });

  const handleTargetLanguageChange = (newTargets: string[]) => {
    if (sourceLanguage) {
      const validTargets = newTargets.filter(target => 
        validateLanguagePair(sourceLanguage, [target])
      );
      setTargetLanguages(validTargets);
    } else {
      setTargetLanguages(newTargets);
    }
    setSelectedEngines([]);
  };

  const handleSourceLanguageChange = async (newSource: string) => {
    setSourceLanguage(newSource);
    if (file) {
      const textContent = await extractTextFromFile(file);
      setWordCount(countWords(textContent, newSource));
    }
    if (targetLanguages.length > 0) {
      const validTargets = targetLanguages.filter(target => 
        validateLanguagePair(newSource, [target])
      );
      setTargetLanguages(validTargets);
    }
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
      let endpoint = '';
      const formData = new FormData();
      formData.append('file', file);

      if (useMultiEngine) {
        endpoint = `${API_BASE_URL}/api/translation-requests/file-multi-engine`;
        formData.append('sourceLanguage', sourceLanguage);
        targetLanguages.forEach(lang => formData.append('targetLanguages', lang));
        selectedEngines.forEach(engine => formData.append('engines', engine));
      } else {
        endpoint = `${API_BASE_URL}/api/translation-requests/file-single-engine`;
        formData.append('sourceLanguage', sourceLanguage);
        targetLanguages.forEach(lang => formData.append('targetLanguages', lang));
      }

      console.log('Submitting file to:', endpoint);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
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
              {sourceLanguage && targetLanguages.length > 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Available pairs: {getAvailableTargetLanguages().map(l => l.label).join(', ')}
                </p>
              )}
            </div>
          </div>

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
            <div 
              {...getRootProps()} 
              className={`p-6 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors
                         ${isDragActive ? 'bg-blue-50 border-blue-500' : 'bg-gray-50 border-gray-300'}`}
            >
              <input {...getInputProps()} />
              {isDetectingLanguage ? (
                <p className="text-blue-600">Analyzing file and detecting language...</p>
              ) : isDragActive ? (
                <p>Drop the file here...</p>
              ) : file ? (
                <p>File "{file.name}" selected. Click or drag to change.</p>
              ) : (
                <p>Drag 'n' drop a file here, or click to select a file</p>
              )}
            </div>
            {file && (
              <div className="mt-2 text-sm text-gray-600">
                <p><strong>Selected:</strong> {file.name}</p>
                <p><strong>Size:</strong> {formatFileSize(file.size)}</p>
                {isProcessingFile && (
                  <p className="text-blue-600">Processing file...</p>
                )}
              </div>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              Supported file types: .txt, .pdf, .docx, .mp3, .wav, .flac, .jpg, .png, .gif
            </p>
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
                        {wordCount.toLocaleString()} {sourceLanguage === 'JA' ? 'characters' : 'words'}
                      </span>
                    )}
                  </p>
                )}
                {file && wordCount > 0 && targetLanguages.length > 0 && (
                  <p><strong>Total {sourceLanguage === 'JA' ? 'Characters' : 'Words'} to Translate:</strong> 
                    <span className="ml-1 font-semibold text-blue-600">
                      {(wordCount * targetLanguages.length * (useMultiEngine ? selectedEngines.length : 1)).toLocaleString()} {sourceLanguage === 'JA' ? 'characters' : 'words'}
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
              isDetectingLanguage ||
              (useMultiEngine && selectedEngines.length === 0)
            }
          >
            {isSubmitting ? 'Submitting...' : 
             isDetectingLanguage ? 'Detecting Language...' :
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
                  { pair: "jpn-eng", label: "JA→EN" },
                  { pair: "eng-jpn", label: "EN→JA" },
                  { pair: "eng-fra", label: "EN→FR" },
                  { pair: "fra-eng", label: "FR→EN" },
                  { pair: "jpn-fra", label: "JA→FR (Pivot)" }
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