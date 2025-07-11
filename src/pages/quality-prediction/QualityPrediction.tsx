// src/pages/quality-prediction/QualityPrediction.tsx

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { MultiSelect } from '@/components/ui/multi-select';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { AlertCircle, ChevronDown, ChevronUp, RefreshCw, TrendingUp } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

// API Configuration
const API_BASE_URL = 'http://localhost:8001';
const API_ENDPOINTS = {
  TRANSLATION_REQUESTS: `${API_BASE_URL}/api/translation-requests`,
  PREDICT_QUALITY: `${API_BASE_URL}/api/quality-assessment/predict-quality`,
  PREDICT_QUALITY_BATCH: `${API_BASE_URL}/api/quality-assessment/predict-quality-batch`,
  PROCESS_ALL_PENDING: `${API_BASE_URL}/api/quality-assessment/process-all-pending`,
  COMET_TRENDS: `${API_BASE_URL}/api/quality-assessment/analytics/comet-trends`,
  HEALTH: `${API_BASE_URL}/api/health`,
};

interface QualityMetrics {
  id: string;
  cometScore: number;
  qualityLabel: string;
  calculationEngine: string;
  createdAt: string;
  hasReference: boolean;
}

interface CometPrediction {
  translationStringId: string;
  cometScore: number;
  qualityLabel: string;
  targetLanguage: string;
}

interface TranslationString {
  id: string;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  status: string;
  isApproved: boolean;
  processingTimeMs: number | null;
  qualityMetrics?: QualityMetrics[];
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
  cometPredictions?: CometPrediction[];
}

interface TrendData {
  label: string;
  averageCometScore: number;
  totalTranslations: number;
  minScore: number;
  maxScore: number;
}

const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JP' },
  { label: 'French', value: 'FR' },
];

const QualityPrediction: React.FC = () => {
  const [translationRequests, setTranslationRequests] = useState<TranslationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [targetLanguageFilter, setTargetLanguageFilter] = useState<string[]>([]);
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<TranslationRequest | null>(null);
  const [selectedRequests, setSelectedRequests] = useState<Set<string>>(new Set());
  const [processingMetrics, setProcessingMetrics] = useState<string | null>(null);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [apiAvailable, setApiAvailable] = useState(true);
  const [trendsData, setTrendsData] = useState<TrendData[]>([]);
  const [trendType, setTrendType] = useState<'language_pair' | 'model' | 'date'>('language_pair');
  const [showTrends, setShowTrends] = useState(false);

  // --- NEW PAGINATION STATE ---
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25); // Default to 25 items
  const itemsPerPageOptions = [25, 50, 100, 0]; // 0 will mean "All"
  // --- END NEW PAGINATION STATE ---

  // Fetch data when component mounts
  useEffect(() => {
    fetchTranslationRequests();
    fetchCometTrends();
  }, []);

  useEffect(() => {
    fetchCometTrends();
  }, [trendType]);

  const getLanguageLabel = (code: string) => {
    return languageOptions.find(lang => lang.value === code)?.label || code;
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      COMPLETED: 'default',
      IN_PROGRESS: 'secondary',
      PENDING: 'outline',
      CANCELLED: 'destructive',
      // Add other statuses if needed, e.g., 'MULTI_ENGINE_REVIEW'
      'MULTI_ENGINE_REVIEW': 'secondary' // Example from CommandCenter
    } as const;

    return (
      <Badge variant={variants[status as keyof typeof variants] || 'outline'}>
        {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase().replace('_', ' ')}
      </Badge>
    );
  };

  const getCometQualityBadge = (score: number | null) => {
    if (score === null) return { variant: 'outline' as const, label: 'N/A' };
    if (score >= 0.8) return { variant: 'default' as const, label: 'Excellent' };
    if (score >= 0.6) return { variant: 'secondary' as const, label: 'Good' };
    if (score >= 0.4) return { variant: 'outline' as const, label: 'Fair' };
    if (score >= 0.2) return { variant: 'destructive' as const, label: 'Poor' };
    return { variant: 'destructive' as const, label: 'Very Poor' };
  };

  // Get quality metrics display for a request
  const getQualityMetricsDisplay = (translationStrings?: TranslationString[]) => {
    if (!translationStrings || translationStrings.length === 0) return null;

    const stringsWithMetrics = translationStrings.filter(str =>
      str.qualityMetrics && str.qualityMetrics.length > 0
    );

    if (stringsWithMetrics.length === 0) return null;

    const avgScore = stringsWithMetrics.reduce((sum, str) => {
      // Ensure we are taking the latest metric if multiple exist
      const latestMetric = str.qualityMetrics!.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())[0];
      return sum + latestMetric.cometScore;
    }, 0) / stringsWithMetrics.length;

    // The qualityLabel should also come from the latest metric or be an aggregate
    // For simplicity, let's derive it from the average score as a fallback or if not present
    const overallQualityLabel = getCometQualityBadge(avgScore).label;

    return {
      avgScore,
      count: stringsWithMetrics.length,
      label: overallQualityLabel // Use derived label for consistency
    };
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
      translationStrings: [{
        id: 'mock-string-1',
        sourceText: 'Hello world',
        translatedText: 'Bonjour le monde',
        targetLanguage: 'FR',
        status: 'COMPLETED',
        isApproved: true,
        processingTimeMs: 100,
        qualityMetrics: [{
          id: 'mock-metric-1',
          cometScore: 0.75,
          qualityLabel: 'Good',
          calculationEngine: 'COMET',
          createdAt: new Date().toISOString(),
          hasReference: true
        }]
      }],
      cometPredictions: [{ // This array is for legacy support
        translationStringId: 'mock-string-1',
        cometScore: 0.75,
        qualityLabel: 'Good',
        targetLanguage: 'FR'
      }]
    }
  ];

  // Fetch translation requests with quality metrics
  const fetchTranslationRequests = async () => {
    setLoading(true);
    setError(null);
    setCurrentPage(1); // Reset to first page on refresh

    try {
      console.log('Fetching translation requests from:', API_ENDPOINTS.TRANSLATION_REQUESTS);

      const response = await fetch(`${API_ENDPOINTS.TRANSLATION_REQUESTS}?include=strings,predictions,qualityMetrics`, {
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

      // Sort requests by date in descending order immediately after fetching
      const sortedRequests = data.sort((a: TranslationRequest, b: TranslationRequest) =>
        new Date(b.requestDate).getTime() - new Date(a.requestDate).getTime()
      );
      setTranslationRequests(sortedRequests);
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

  // Fetch COMET trends data
  const fetchCometTrends = async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.COMET_TRENDS}?group_by=${trendType}&days=30`);

      if (!response.ok) {
        throw new Error('Failed to fetch trends');
      }

      const data = await response.json();
      setTrendsData(data.trends || []);
    } catch (err) {
      console.error('Failed to fetch COMET trends:', err);
      setTrendsData([]);
    }
  };

  // Predict quality using COMET for single request
  const predictQuality = async (requestId: string) => {
    setProcessingMetrics(requestId);
    try {
      console.log('Predicting quality for request:', requestId);

      const response = await fetch(`${API_ENDPOINTS.PREDICT_QUALITY}?request_id=${requestId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to predict quality');
      }

      const result = await response.json();
      console.log('Quality prediction result:', result);

      // Force refresh the data to show updated predictions
      await fetchTranslationRequests();

      // Clear any previous errors
      setError(null);

    } catch (err) {
      console.error('Failed to predict quality:', err);
      setError(err instanceof Error ? err.message : 'Failed to predict quality');
    } finally {
      setProcessingMetrics(null);
    }
  };

  // Batch predict quality for multiple requests
  const predictQualityBatch = async () => {
    if (selectedRequests.size === 0) {
      setError('Please select at least one translation request.');
      return;
    }

    setBatchProcessing(true);
    try {
      const requestIds = Array.from(selectedRequests);
      console.log('Batch predicting quality for requests:', requestIds);

      const response = await fetch(API_ENDPOINTS.PREDICT_QUALITY_BATCH, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestIds),
      });

      if (!response.ok) {
        throw new Error('Failed to batch predict quality');
      }

      const result = await response.json();
      console.log('Batch quality prediction result:', result);

      // Clear selection and refresh data
      setSelectedRequests(new Set());
      await fetchTranslationRequests();

      setError(null);

    } catch (err) {
      console.error('Failed to batch predict quality:', err);
      setError(err instanceof Error ? err.message : 'Failed to batch predict quality');
    } finally {
      setBatchProcessing(false);
    }
  };

  // Process all pending quality assessments
  const processAllPending = async () => {
    setBatchProcessing(true);
    try {
      console.log('Processing all pending quality assessments');

      const response = await fetch(API_ENDPOINTS.PROCESS_ALL_PENDING, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to process all pending');
      }

      const result = await response.json();
      console.log('Process all pending result:', result);

      // Refresh data to show updated metrics
      await fetchTranslationRequests();

      setError(null);

    } catch (err) {
      console.error('Failed to process all pending:', err);
      setError(err instanceof Error ? err.message : 'Failed to process all pending');
    } finally {
      setBatchProcessing(false);
    }
  };

  // Toggle request selection for batch operations
  const toggleRequestSelection = (requestId: string) => {
    const newSelection = new Set(selectedRequests);
    if (newSelection.has(requestId)) {
      newSelection.delete(requestId);
    } else {
      newSelection.add(requestId);
    }
    setSelectedRequests(newSelection);
  };

  // Check if request has COMET predictions (legacy support)
  const hasPredictions = (request: TranslationRequest) => {
    return request.cometPredictions && request.cometPredictions.length > 0;
  };

  // Get average COMET score for a request (legacy support)
  const getAverageCometScore = (request: TranslationRequest) => {
    if (!hasPredictions(request)) return null;

    const scores = request.cometPredictions!.map(p => p.cometScore);
    return scores.reduce((sum, score) => sum + score, 0) / scores.length;
  };

  // Check if request has quality metrics or predictions
  const hasQualityData = (request: TranslationRequest) => {
    return getQualityMetricsDisplay(request.translationStrings) !== null || hasPredictions(request);
  };

  // Filter and sort requests (this now returns the full filtered/sorted list)
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

  // --- NEW PAGINATION CALCULATION FOR THIS TABLE ---
  const totalFilteredAndSortedRequests = filteredAndSortedRequests.length;
  const totalPages = itemsPerPage === 0
    ? 1
    : Math.ceil(totalFilteredAndSortedRequests / itemsPerPage);

  const paginatedRequests = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = itemsPerPage === 0 ? totalFilteredAndSortedRequests : startIndex + itemsPerPage;
    return filteredAndSortedRequests.slice(startIndex, endIndex);
  }, [filteredAndSortedRequests, currentPage, itemsPerPage, totalFilteredAndSortedRequests]);
  // --- END NEW PAGINATION CALCULATION ---


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
    const qualityDisplay = getQualityMetricsDisplay(request.translationStrings);

    if (qualityDisplay) {
      // Use quality metrics data
      return request.translationStrings!
        .filter(str => str.qualityMetrics && str.qualityMetrics.length > 0)
        .map(str => ({
          language: getLanguageLabel(str.targetLanguage),
          COMET: str.qualityMetrics![0].cometScore * 100, // Assuming first metric is the relevant one
          qualityLabel: str.qualityMetrics![0].qualityLabel
        }));
    }

    if (hasPredictions(request)) {
      // Use legacy predictions data
      return request.cometPredictions!.map(prediction => ({
        language: getLanguageLabel(prediction.targetLanguage),
        COMET: prediction.cometScore * 100,
        qualityLabel: prediction.qualityLabel
      }));
    }

    return [];
  };

  const formatScore = (score: number | null) => {
    return score ? (score * 100).toFixed(1) + '%' : 'N/A';
  };

  const getCometColor = (score: number | null) => {
    if (score === null) return 'text-gray-400';
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-blue-600';
    if (score >= 0.4) return 'text-yellow-600';
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
        <div className="flex space-x-2">
          <Button
            onClick={() => setShowTrends(!showTrends)}
            variant="outline"
          >
            <TrendingUp className="h-4 w-4 mr-2" />
            {showTrends ? 'Hide Trends' : 'Show Trends'}
          </Button>
          <Button onClick={fetchTranslationRequests} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
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

      {/* Batch Operations */}
      {selectedRequests.size > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <p className="text-blue-800">
                  {selectedRequests.size} request(s) selected
                </p>
              </div>
              <div className="flex space-x-2">
                <Button
                  onClick={predictQualityBatch}
                  disabled={batchProcessing}
                  size="sm"
                >
                  {batchProcessing ? (
                    <>
                      <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    'Predict Quality (Batch)'
                  )}
                </Button>
                <Button
                  onClick={() => setSelectedRequests(new Set())}
                  variant="outline"
                  size="sm"
                >
                  Clear Selection
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Process All Pending */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Batch Processing</h3>
              <p className="text-sm text-muted-foreground">
                Process quality assessment for all translation requests without quality metrics
              </p>
            </div>
            <Button
              onClick={processAllPending}
              disabled={batchProcessing}
              variant="secondary"
            >
              {batchProcessing ? (
                <>
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  Processing All...
                </>
              ) : (
                'Process All Pending'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* COMET Trends Section */}
      {showTrends && (
        <Card>
          <CardHeader>
            <CardTitle>COMET Quality Trends</CardTitle>
            <div className="flex space-x-2">
              <Button
                variant={trendType === 'language_pair' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendType('language_pair')}
              >
                By Language Pair
              </Button>
              <Button
                variant={trendType === 'model' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendType('model')}
              >
                By Model
              </Button>
              <Button
                variant={trendType === 'date' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendType('date')}
              >
                Over Time
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={trendsData}>
                <XAxis dataKey="label" />
                <YAxis domain={[0, 1]} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
                <Tooltip formatter={(value) => [`${(Number(value) * 100).toFixed(1)}%`, 'Average COMET Score']} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="averageCometScore"
                  stroke="#8884d8"
                  strokeWidth={2}
                  name="Average COMET Score"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

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
            {/* --- NEW PAGINATION CONTROLS FOR THIS TABLE --- */}
            <div className="text-sm text-muted-foreground flex justify-between items-center w-full mt-2">
                <span>Showing {paginatedRequests.length} of {totalFilteredAndSortedRequests} requests</span>
                <div className="flex items-center space-x-2">
                    <Label htmlFor="items-per-page" className="text-sm font-medium">Items per page:</Label>
                    <Select
                        value={String(itemsPerPage)}
                        onValueChange={(value) => {
                            setItemsPerPage(Number(value));
                            setCurrentPage(1); // Reset to first page on items per page change
                        }}
                    >
                        <SelectTrigger className="w-[100px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {itemsPerPageOptions.map((option, index) => (
                                <SelectItem key={index} value={String(option)}>
                                    {option === 0 ? 'All' : option}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                    >
                        Previous
                    </Button>
                    <span className="text-sm">Page {currentPage} of {totalPages}</span>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        disabled={currentPage === totalPages || totalPages === 0}
                    >
                        Next
                    </Button>
                </div>
            </div>
            {/* --- END NEW PAGINATION CONTROLS --- */}
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <input
                    type="checkbox"
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedRequests(new Set(filteredAndSortedRequests.map(r => r.id)));
                      } else {
                        setSelectedRequests(new Set());
                      }
                    }}
                    checked={selectedRequests.size === filteredAndSortedRequests.length && filteredAndSortedRequests.length > 0}
                  />
                </TableHead>
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
                <TableHead>COMET Quality Prediction</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedRequests.map((request) => { // Use paginatedRequests here
                const qualityDisplay = getQualityMetricsDisplay(request.translationStrings);
                const avgScore = getAverageCometScore(request);

                return (
                  <TableRow
                    key={request.id}
                    className={selectedRequest?.id === request.id ? 'bg-muted/50' : 'hover:bg-muted/30'}
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selectedRequests.has(request.id)}
                        onChange={() => toggleRequestSelection(request.id)}
                      />
                    </TableCell>
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
                      {qualityDisplay ? (
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center space-x-2">
                            <span className={`font-semibold ${getCometColor(qualityDisplay.avgScore)}`}>
                              COMET: {formatScore(qualityDisplay.avgScore)}
                            </span>
                            <Badge
                              variant={getCometQualityBadge(qualityDisplay.avgScore).variant}
                              className="text-xs"
                            >
                              {qualityDisplay.label}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {qualityDisplay.count} prediction(s)
                          </div>
                        </div>
                      ) : hasPredictions(request) ? (
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center space-x-2">
                            <span className={`font-semibold ${getCometColor(avgScore)}`}>
                              COMET: {formatScore(avgScore)}
                            </span>
                            <Badge
                              variant={getCometQualityBadge(avgScore).variant}
                              className="text-xs"
                            >
                              {getCometQualityBadge(avgScore).label}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {request.cometPredictions!.length} prediction(s)
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs">Not predicted</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex space-x-2">
                        {hasQualityData(request) ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedRequest(request)}
                          >
                            View Predictions
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => predictQuality(request.id)}
                            disabled={processingMetrics === request.id || request.status !== 'COMPLETED'}
                          >
                            {processingMetrics === request.id ? (
                              <>
                                <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                Predicting...
                              </>
                            ) : (
                              'Predict Quality'
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

      {/* Selected Request COMET Predictions */}
      {selectedRequest && hasQualityData(selectedRequest) && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                COMET Quality Predictions for {selectedRequest.fileName}
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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {(() => {
                  const qualityDisplay = getQualityMetricsDisplay(selectedRequest.translationStrings);

                  if (qualityDisplay && selectedRequest.translationStrings) {
                    return selectedRequest.translationStrings
                      .filter(str => str.qualityMetrics && str.qualityMetrics.length > 0)
                      .map((str, index) => {
                        const metric = str.qualityMetrics![0]; // Assuming first metric is the relevant one
                        return (
                          <div key={index} className="text-center">
                            <div className="text-2xl font-bold mb-2">
                              <span className={getCometColor(metric.cometScore)}>
                                {formatScore(metric.cometScore)}
                              </span>
                            </div>
                            <div className="text-sm font-medium text-muted-foreground">
                              {getLanguageLabel(str.targetLanguage)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              Neural-based quality prediction
                            </div>
                            <Badge
                              variant={getCometQualityBadge(metric.cometScore).variant}
                              className="mt-2"
                            >
                              {metric.qualityLabel}
                            </Badge>
                          </div>
                        );
                      });
                  }

                  if (hasPredictions(selectedRequest)) {
                    return selectedRequest.cometPredictions!.map((prediction, index) => (
                      <div key={index} className="text-center">
                        <div className="text-2xl font-bold mb-2">
                          <span className={getCometColor(prediction.cometScore)}>
                            {formatScore(prediction.cometScore)}
                          </span>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">
                          {getLanguageLabel(prediction.targetLanguage)}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Neural-based quality prediction
                        </div>
                        <Badge
                          variant={getCometQualityBadge(prediction.cometScore).variant}
                          className="mt-2"
                        >
                          {prediction.qualityLabel}
                        </Badge>
                      </div>
                    ));
                  }

                  return null;
                })()}
              </div>
            </CardContent>
          </Card>

          {/* COMET Prediction Chart */}
          <Card>
            <CardHeader>
              <CardTitle>COMET Quality Scores by Language</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={getChartData(selectedRequest)}>
                  <XAxis dataKey="language" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, 'COMET Score']} />
                  <Legend />
                  <Bar dataKey="COMET" fill="#8884d8" name="COMET Quality Score" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Clear Selection */}
          <div className="flex justify-center">
            <Button variant="outline" onClick={() => setSelectedRequest(null)}>
              Clear Selection
            </Button>
          </div>
        </div>
      )}

      {/* No Selection Message */}
      {!selectedRequest && (
        <Card>
          <CardContent className="text-center py-8">
            <p className="text-muted-foreground">
              Select a translation request from the table above to view COMET quality predictions.
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