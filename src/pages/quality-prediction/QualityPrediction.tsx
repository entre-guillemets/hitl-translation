// src/pages/quality-prediction/QualityPrediction.tsx

"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MultiSelect } from '@/components/ui/multi-select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { AlertCircle, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

// API Configuration
const API_BASE_URL = 'http://localhost:8001';
const API_ENDPOINTS = {
  TRANSLATION_REQUESTS: `${API_BASE_URL}/api/translation-requests`,
  QUALITY_METRICS_CALCULATE: `${API_BASE_URL}/api/quality-metrics/calculate`,
  HEALTH: `${API_BASE_URL}/api/health`,
};

// Types based on Prisma schema
interface QualityMetrics {
  id: string;
  metricXScore: number | null;
  metricXConfidence: number | null;
  metricXMode: string | null;
  metricXVariant: string | null;
  bleuScore: number | null;
  cometScore: number | null;
  terScore: number | null;
  qualityLabel: string | null;
}

interface TranslationString {
  id: string;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  status: string;
  isApproved: boolean;
  processingTimeMs: number | null;
}

interface TranslationRequest {
  id: string;
  sourceLanguage: string;
  targetLanguages: string[];
  languagePair: string;
  wordCount: number;
  requestDate: string;
  requestTime: string;
  fileName: string;
  status: string;
  mtModel: string;
  translationStrings?: TranslationString[];
  qualityMetrics?: QualityMetrics | QualityMetrics[]; // Handle both formats
}

const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JP' },
  { label: 'French', value: 'FR' },
];

export const QualityPrediction: React.FC = () => {
  const [translationRequests, setTranslationRequests] = useState<TranslationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [targetLanguageFilter, setTargetLanguageFilter] = useState<string[]>([]);
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<TranslationRequest | null>(null);
  const [processingMetrics, setProcessingMetrics] = useState<string | null>(null);
  const [apiAvailable, setApiAvailable] = useState(true);

  // Fetch data when component mounts
  useEffect(() => {
    fetchTranslationRequests();
  }, []);

  const getLanguageLabel = (code: string) => {
    return languageOptions.find(lang => lang.value === code)?.label || code;
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      COMPLETED: 'default',
      IN_PROGRESS: 'secondary',
      PENDING: 'outline',
      CANCELLED: 'destructive'
    } as const;
    
    return (
      <Badge variant={variants[status as keyof typeof variants] || 'outline'}>
        {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase().replace('_', ' ')}
      </Badge>
    );
  };

  const getMetricXQualityBadge = (score: number | null) => {
    if (score === null) return { variant: 'outline' as const, label: 'N/A' };
    if (score <= 7) return { variant: 'default' as const, label: 'Excellent' };
    if (score <= 12) return { variant: 'secondary' as const, label: 'Good' };
    if (score <= 18) return { variant: 'outline' as const, label: 'Fair' };
    return { variant: 'destructive' as const, label: 'Poor' };
  };

  // Mock data fallback
  const getMockData = (): TranslationRequest[] => [
    {
      id: 'mock-1',
      sourceLanguage: 'EN',
      targetLanguages: ['FR'],
      languagePair: 'en-fr',
      wordCount: 150,
      requestDate: new Date(Date.now() - 86400000).toISOString(),
      requestTime: new Date(Date.now() - 86400000).toISOString(),
      fileName: 'sample_document.txt',
      status: 'COMPLETED',
      mtModel: 'MARIAN_MT_EN_FR',
      translationStrings: [],
      qualityMetrics: {
        id: 'metric-1',
        metricXScore: 8.5,
        metricXConfidence: 0.92,
        metricXMode: 'REFERENCE_FREE',
        metricXVariant: 'METRICX_24_HYBRID',
        bleuScore: 0.78,
        cometScore: 0.82,
        terScore: 0.15,
        qualityLabel: 'GOOD'
      }
    }
  ];

  // Fetch translation requests with error handling and debugging
  const fetchTranslationRequests = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('Fetching translation requests from:', API_ENDPOINTS.TRANSLATION_REQUESTS);
      
      const response = await fetch(`${API_ENDPOINTS.TRANSLATION_REQUESTS}?include=strings,metrics`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      });
      
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const responseText = await response.text();
        console.error('Non-JSON response received:', responseText);
        throw new Error('Server returned non-JSON response');
      }
      
      const data = await response.json();
      console.log('Raw API response:', data);
      console.log('Number of requests:', data.length);
      
      // Debug first request's quality metrics
      if (data.length > 0) {
        console.log('First request qualityMetrics:', data[0]?.qualityMetrics);
        console.log('First request structure:', Object.keys(data[0]));
      }
      
      setTranslationRequests(data);
      setApiAvailable(true);
      setError(null);
      
    } catch (err) {
      console.error('API fetch failed:', err);
      setApiAvailable(false);
      
      // Use mock data as fallback
      const mockData = getMockData();
      setTranslationRequests(mockData);
      setError(`Backend connection failed - showing sample data. Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  // Calculate quality metrics with better feedback
  const calculateMetrics = async (requestId: string) => {
    setProcessingMetrics(requestId);
    try {
      console.log('Calculating metrics for request:', requestId);
      
      const response = await fetch(API_ENDPOINTS.QUALITY_METRICS_CALCULATE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requestId }),
      });
  
      if (!response.ok) {
        throw new Error('Failed to calculate metrics');
      }
  
      const result = await response.json();
      console.log('Metrics calculation result:', result);
  
      // Force refresh the data to show updated metrics
      await fetchTranslationRequests();
      
      // Clear any previous errors
      setError(null);
      
    } catch (err) {
      console.error('Failed to calculate metrics:', err);
      setError(err instanceof Error ? err.message : 'Failed to calculate metrics');
    } finally {
      setProcessingMetrics(null);
    }
  };

  // Handle both single object and array formats for quality metrics
  const hasMetrics = (request: TranslationRequest) => {
    if (!request.qualityMetrics) return false;
    
    if (Array.isArray(request.qualityMetrics)) {
      return request.qualityMetrics.length > 0;
    }
    
    return true; // Single object exists
  };

  const getAverageMetrics = (request: TranslationRequest) => {
    if (!hasMetrics(request)) return null;
    
    // Handle both single object and array formats
    const metrics = Array.isArray(request.qualityMetrics) 
      ? request.qualityMetrics[0] 
      : request.qualityMetrics;
    
    if (!metrics) return null;
    
    return {
      metricX: metrics.metricXScore,
      bleu: metrics.bleuScore,
      comet: metrics.cometScore,
      ter: metrics.terScore,
      confidence: metrics.metricXConfidence,
      mode: metrics.metricXMode,
      variant: metrics.metricXVariant,
      qualityLabel: metrics.qualityLabel
    };
  };

  // Filter and sort requests
  const filteredAndSortedRequests = useMemo(() => {
    let filtered = translationRequests;
    
    if (targetLanguageFilter.length > 0) {
      filtered = filtered.filter(request => 
        request.targetLanguages.some(lang => targetLanguageFilter.includes(lang))
      );
    }

    if (sortConfig !== null) {
      filtered = [...filtered].sort((a, b) => {
        let aValue: any = a[sortConfig.key as keyof TranslationRequest];
        let bValue: any = b[sortConfig.key as keyof TranslationRequest];

        if (Array.isArray(aValue) && Array.isArray(bValue)) {
          aValue = aValue.join(', ');
          bValue = bValue.join(', ');
        }

        if (sortConfig.key === 'requestDate') {
          aValue = new Date(aValue);
          bValue = new Date(bValue);
        }

        if (aValue < bValue) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }

    return filtered;
  }, [translationRequests, targetLanguageFilter, sortConfig]);

  const requestSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key: string) => {
    if (!sortConfig || sortConfig.key !== key) {
      return <ChevronUp className="h-4 w-4 opacity-30" />;
    }
    return sortConfig.direction === 'asc' ? 
      <ChevronUp className="h-4 w-4" /> : 
      <ChevronDown className="h-4 w-4" />;
  };

  // Generate chart data for selected request
  const getChartData = (request: TranslationRequest) => {
    const metrics = getAverageMetrics(request);
    if (!metrics) return [];
    
    return request.targetLanguages.map(lang => ({
      language: getLanguageLabel(lang),
      BLEU: metrics.bleu ? metrics.bleu * 100 : 0,
      COMET: metrics.comet ? metrics.comet * 100 : 0,
      TER: metrics.ter ? metrics.ter * 100 : 0,
      MetricX: metrics.metricX || 0,
    }));
  };

  const formatScore = (score: number | null) => {
    return score ? score.toFixed(1) : 'N/A';
  };

  const getScoreColor = (score: number | null, isInverted = false) => {
    if (score === null) return 'text-gray-400';
    const threshold = isInverted ? 0.2 : 0.8;
    const comparison = isInverted ? score <= threshold : score >= threshold;
    
    if (comparison) return 'text-green-600';
    if (isInverted ? score <= 0.3 : score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getMetricXColor = (score: number | null) => {
    if (score === null) return 'text-gray-400';
    if (score <= 7) return 'text-green-600';
    if (score <= 12) return 'text-blue-600';
    if (score <= 18) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Quality Prediction</h1>
        </div>
        <Card>
          <CardContent className="text-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
            <p>Loading translation requests...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Quality Prediction</h1>
        <Button onClick={fetchTranslationRequests} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Error/Warning Banner */}
      {error && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-5 w-5 text-yellow-600" />
              <p className="text-yellow-800">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Connection Status */}
      <Card className={apiAvailable ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-2">
            <div className={`h-3 w-3 rounded-full ${apiAvailable ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <p className={apiAvailable ? "text-green-800" : "text-red-800"}>
              {apiAvailable ? 'Connected to FastAPI Backend' : 'Backend Connection Failed'}
            </p>
            <span className="text-sm text-gray-600">({API_BASE_URL})</span>
          </div>
        </CardContent>
      </Card>

      {/* Translation Requests Table */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>
              Translation Requests {!apiAvailable && '(Sample Data)'}
            </CardTitle>
          </div>
          <div className="flex items-center space-x-4 mt-2">
            <div className="flex-1 max-w-md">
              <label className="block text-sm font-medium mb-2">Filter by Target Languages</label>
              <MultiSelect
                options={languageOptions}
                selectedValues={targetLanguageFilter}
                onSelectionChange={setTargetLanguageFilter}
                placeholder="Filter by target languages"
              />
            </div>
            <div className="text-sm text-muted-foreground">
              Showing {filteredAndSortedRequests.length} of {translationRequests.length} requests
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead 
                  onClick={() => requestSort('requestDate')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>Request Date</span>
                    {getSortIcon('requestDate')}
                  </div>
                </TableHead>
                <TableHead 
                  onClick={() => requestSort('sourceLanguage')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>Source Language</span>
                    {getSortIcon('sourceLanguage')}
                  </div>
                </TableHead>
                <TableHead 
                  onClick={() => requestSort('targetLanguages')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>Target Languages</span>
                    {getSortIcon('targetLanguages')}
                  </div>
                </TableHead>
                <TableHead 
                  onClick={() => requestSort('fileName')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>File Name</span>
                    {getSortIcon('fileName')}
                  </div>
                </TableHead>
                <TableHead 
                  onClick={() => requestSort('wordCount')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>Word Count</span>
                    {getSortIcon('wordCount')}
                  </div>
                </TableHead>
                <TableHead 
                  onClick={() => requestSort('status')} 
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <div className="flex items-center space-x-1">
                    <span>Status</span>
                    {getSortIcon('status')}
                  </div>
                </TableHead>
                <TableHead>Quality Metrics</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAndSortedRequests.map((request) => {
                const metrics = getAverageMetrics(request);
                return (
                  <TableRow 
                    key={request.id}
                    className={selectedRequest?.id === request.id ? 'bg-muted/50' : 'hover:bg-muted/30'}
                  >
                    <TableCell>{new Date(request.requestDate).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {getLanguageLabel(request.sourceLanguage)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {request.targetLanguages.map((lang, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            {getLanguageLabel(lang)}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{request.fileName}</TableCell>
                    <TableCell className="font-semibold">
                      {request.wordCount.toLocaleString()} words
                    </TableCell>
                    <TableCell>{getStatusBadge(request.status)}</TableCell>
                    <TableCell>
                      {metrics ? (
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center space-x-2">
                            <span>MetricX:</span>
                            <span className={`font-semibold ${getMetricXColor(metrics.metricX)}`}>
                              {formatScore(metrics.metricX)}
                            </span>
                            <Badge 
                              variant={getMetricXQualityBadge(metrics.metricX).variant}
                              className="text-xs"
                            >
                              {getMetricXQualityBadge(metrics.metricX).label}
                            </Badge>
                          </div>
                          <div>BLEU: <span className="font-semibold">{formatScore(metrics.bleu ? metrics.bleu * 100 : null)}%</span></div>
                          <div>COMET: <span className="font-semibold">{formatScore(metrics.comet ? metrics.comet * 100 : null)}%</span></div>
                          <div>TER: <span className="font-semibold">{formatScore(metrics.ter ? metrics.ter * 100 : null)}%</span></div>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs">Not calculated</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex space-x-2">
                        {hasMetrics(request) ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedRequest(request)}
                          >
                            View Metrics
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => calculateMetrics(request.id)}
                            disabled={processingMetrics === request.id || request.status !== 'COMPLETED'}
                          >
                            {processingMetrics === request.id ? (
                              <>
                                <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                Calculating...
                              </>
                            ) : (
                              'Calculate Metrics'
                            )}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Selected Request Metrics */}
      {selectedRequest && hasMetrics(selectedRequest) && (
        <div className="space-y-6">
          {(() => {
            const metrics = getAverageMetrics(selectedRequest);
            return (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>
                      Quality Metrics for {selectedRequest.fileName}
                    </CardTitle>
                    <div className="text-sm text-muted-foreground">
                      {getLanguageLabel(selectedRequest.sourceLanguage)} → {selectedRequest.targetLanguages.map(lang => getLanguageLabel(lang)).join(', ')}
                      <span className="ml-4">
                        <strong>Word Count:</strong> {selectedRequest.wordCount.toLocaleString()} words
                      </span>
                      <span className="ml-4">
                        <strong>Model:</strong> {selectedRequest.mtModel}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                      {/* MetricX Score */}
                      <div className="text-center">
                        <div className="text-2xl font-bold mb-2">
                          <span className={getMetricXColor(metrics?.metricX || null)}>
                            {formatScore(metrics?.metricX || null)}
                          </span>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">MetricX Score</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Lower is better
                        </div>
                        <Badge 
                          variant={getMetricXQualityBadge(metrics?.metricX || null).variant}
                          className="mt-2"
                        >
                          {getMetricXQualityBadge(metrics?.metricX || null).label}
                        </Badge>
                      </div>

                      {/* BLEU Score */}
                      <div className="text-center">
                        <div className="text-2xl font-bold mb-2">
                          <span className={getScoreColor(metrics?.bleu || null)}>
                            {formatScore(metrics?.bleu ? metrics.bleu * 100 : null)}%
                          </span>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">BLEU Score</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Measures translation quality
                        </div>
                      </div>

                      {/* COMET Score */}
                      <div className="text-center">
                        <div className="text-2xl font-bold mb-2">
                          <span className={getScoreColor(metrics?.comet || null)}>
                            {formatScore(metrics?.comet ? metrics.comet * 100 : null)}%
                          </span>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">COMET Score</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Neural-based evaluation
                        </div>
                      </div>

                      {/* TER Score */}
                      <div className="text-center">
                        <div className="text-2xl font-bold mb-2">
                          <span className={getScoreColor(metrics?.ter || null, true)}>
                            {formatScore(metrics?.ter ? metrics.ter * 100 : null)}%
                          </span>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">TER Score</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Translation error rate (lower is better)
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Bar Chart */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Quality Metrics by Target Language</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={getChartData(selectedRequest)}>
                          <XAxis dataKey="language" />
                          <YAxis />
                          <Tooltip formatter={(value, name) => {
                            if (name === 'MetricX') {
                              return [`${Number(value).toFixed(1)}`, name];
                            }
                            return [`${Number(value).toFixed(1)}%`, name];
                          }} />
                          <Legend />
                          <Bar dataKey="MetricX" fill="#ff6b6b" name="MetricX (lower=better)" />
                          <Bar dataKey="BLEU" fill="#8884d8" />
                          <Bar dataKey="COMET" fill="#82ca9d" />
                          <Bar dataKey="TER" fill="#ffc658" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  {/* Line Chart */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Quality Trends</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={getChartData(selectedRequest)}>
                          <XAxis dataKey="language" />
                          <YAxis />
                          <Tooltip formatter={(value, name) => {
                            if (name === 'MetricX') {
                              return [`${Number(value).toFixed(1)}`, name];
                            }
                            return [`${Number(value).toFixed(1)}%`, name];
                          }} />
                          <Legend />
                          <Line type="monotone" dataKey="MetricX" stroke="#ff6b6b" strokeWidth={2} name="MetricX (lower=better)" />
                          <Line type="monotone" dataKey="BLEU" stroke="#8884d8" strokeWidth={2} />
                          <Line type="monotone" dataKey="COMET" stroke="#82ca9d" strokeWidth={2} />
                          <Line type="monotone" dataKey="TER" stroke="#ffc658" strokeWidth={2} />
                        </LineChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                {/* MetricX Details */}
                <Card>
                  <CardHeader>
                    <CardTitle>MetricX Analysis Details</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {metrics?.confidence ? metrics.confidence.toFixed(2) : 'N/A'}
                        </div>
                        <div className="text-sm text-muted-foreground">Confidence Score</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {metrics?.mode || 'N/A'}
                        </div>
                        <div className="text-sm text-muted-foreground">Evaluation Mode</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {metrics?.variant || 'N/A'}
                        </div>
                        <div className="text-sm text-muted-foreground">Model Variant</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Clear Selection */}
                <div className="flex justify-center">
                  <Button variant="outline" onClick={() => setSelectedRequest(null)}>
                    Clear Selection
                  </Button>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* No Selection Message */}
      {!selectedRequest && (
        <Card>
          <CardContent className="text-center py-8">
            <p className="text-muted-foreground">
              Select a translation request from the table above to view quality metrics and predictions.
            </p>
            {!apiAvailable && (
              <p className="text-sm text-yellow-600 mt-2">
                Note: Currently showing sample data. Backend connection failed.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default QualityPrediction;
