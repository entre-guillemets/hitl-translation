// src/pages/QualityDashboard.tsx

"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertTriangle, Circle, Download, RefreshCw } from 'lucide-react'; 
import React, { useEffect, useMemo, useState } from 'react';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '../../components/ui/chart';

// Import Dialog components for modal
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';

// API Configuration
const API_BASE_URL = 'http://localhost:8001';

// Types (assuming these are consistent with your backend types)
interface DashboardData {
  modelPerformance: ModelPerformanceData;
  humanPreferences: HumanPreferenceData;
  annotations: AnnotationData;
  multiEngine: MultiEngineData;
  qualityScores: QualityScoreData;
  operational: OperationalData;
  tmGlossary: TMGlossaryData;
}

interface PostEditMetricsData {
  languagePairMetrics: LanguagePairMetricEntry[];
  correlationMatrix: CorrelationEntry[];
  totalPostEdits: number;
}

interface LanguagePairMetricEntry {
  languagePair: string;
  avgBleu: number;
  avgComet: number;
  avgTer: number; // This comes as a percentage (e.g., 50.0 for 50%) from backend
  count: number;
}

interface ModelPerformanceData {
  leaderboard: ModelLeaderboardEntry[];
  performanceOverTime: PerformanceTimeEntry[];
  modelComparison: ModelComparisonEntry[];
}

interface ModelLeaderboardEntry {
  name?: string;          
  type?: string;          
  model: string;
  engineType: string;
  avgBleu: number;
  avgComet: number;
  avgTer: number; // This comes as a percentage (e.g., 50.0 for 50%) from backend
  avgMetricX: number;
  totalTranslations: number;
  languagePairs?: string[];  
  models?: string[];         
  confidenceInterval: {
    bleuLow: number;
    bleuHigh: number;
    cometLow: number;
    cometHigh: number;
  };
}

interface PerformanceTimeEntry {
  date: string;
  model: string;
  bleuScore: number;
  cometScore: number;
  metricXScore: number;
  translationCount: number;
  languagePair?: string;
  requestId?: string;
}

interface HumanPreferenceData {
  enginePreferences: EnginePreferenceEntry[];
  reviewerBehavior: ReviewerBehaviorEntry[];
  preferenceReasons: PreferenceReasonEntry[];
}

interface EnginePreferenceEntry {
  engine: string;
  selectionCount: number;
  avgRating: number;
  languagePair: string;
  preferenceReason: string;
  overallSatisfaction: number;
}

interface ReviewerBehaviorEntry {
  reviewerExpertise: string;
  avgTimeToReview: number;
  avgCognitiveLoad: number;
  approvalType: string;
  count: number;
}

interface AnnotationData {
  errorHeatmap: ErrorHeatmapEntry[];
  severityBreakdown: SeverityBreakdownEntry[];
  spanAnalysis: SpanAnalysisEntry[];
}

interface ErrorHeatmapEntry {
  model: string;
  category: string;
  errorType: string;
  severity: string;
  count: number;
  painIndex: number;
}

interface MultiEngineData {
  selectionTrends: SelectionTrendEntry[];
  pivotQuality: PivotQualityEntry[];
  interRaterAgreement: InterRaterEntry[];
}

interface QualityScoreData {
  evaluationModes: EvaluationModeEntry[];
  correlationMatrix: CorrelationEntry[];
  scoreDistribution: ScoreDistributionEntry[];
}

interface OperationalData {
  processingTimes: ProcessingTimeEntry[];
  systemHealth: SystemHealthEntry[];
  modelUtilization: ModelUtilizationEntry[];
}

interface TMGlossaryData {
  tmImpact: TMImpactEntry[];
  glossaryUsage: GlossaryUsageEntry[];
  termOverrides: TermOverrideEntry[];
}

// Additional interface definitions
interface ModelComparisonEntry {
  model: string;
  metric: string;
  value: number;
}

interface SeverityBreakdownEntry {
  severity: string;
  count: number;
  model: string;
}

interface SpanAnalysisEntry {
  id: string;
  sourceSpan: { start: number; end: number };
  targetSpan: { start: number; end: number };
  category: string;
  suggestedFix: string;
  confidence: number;
}

interface SelectionTrendEntry {
  date: string;
  selectionMethod: string;
  count: number;
  modelCombination: string;
}

interface PivotQualityEntry {
  modelCombination: string;
  directQuality: number;
  pivotQuality: number;
  intermediateQuality: number;
}

interface InterRaterEntry {
  annotatorPair: string;
  agreement: number;
  category: string;
}

interface EvaluationModeEntry {
  mode: string;
  avgScore: number;
  confidence: number;
  count: number;
}

interface CorrelationEntry {
  metric1: string;
  metric2: string;
  correlation: number;
  pValue: number;
}

interface ScoreDistributionEntry {
  metric: string;
  scoreRange: string;
  count: number;
  percentage: number;
}

interface ProcessingTimeEntry {
  model: string;
  engineType: string;
  wordCountBucket: string;
  avgProcessingTime: number;
  count: number;
}

interface SystemHealthEntry {
  model: string;
  isActive: boolean;
  lastUsed: string;
  totalTranslations: number;
  avgProcessingTime: number;
}

interface ModelUtilizationEntry {
  model: string;
  utilizationRate: number;
  idleDays: number;
  needsUpdate: boolean;
}

interface TMImpactEntry {
  matchPercentage: string;
  avgQualityScore: number;
  timeSaved: number;
  approvalRate: number;
}

interface GlossaryUsageEntry {
  term: string;
  usageCount: number;
  overrideRate: number;
  qualityImpact: number;
}

interface TermOverrideEntry {
  term: string;
  originalTranslation: string;
  overrideTranslation: string;
  frequency: number;
  qualityDelta: number;
}

interface PreferenceReasonEntry {
  reason: string;
  count: number;
  avgSatisfaction: number;
}

interface TranslatorImpactData {
  comparisons: TranslationComparisonEntry[];
  summary: TranslatorSummaryEntry[];
}

interface TranslationComparisonEntry {
  id: string;
  sourceText: string;
  originalMT: string;
  humanEdited: string;
  translatorId?: string;
  languagePair: string;
  jobId: string;
  jobName: string;
  editDistance: number;
  improvementScore: number;
  editType: 'minor' | 'moderate' | 'major';
  timestamp: string;
  processingTime?: number;
}

interface TranslatorSummaryEntry {
  translatorId: string;
  totalEdits: number;
  avgImprovementScore: number;
  avgEditDistance: number;
  languagePairs: string[];
  editTypes: {
    minor: number;
    moderate: number;
    major: number;
  };
}

// Chart configurations
const performanceChartConfig = {
  bleuScore: {
    label: "BLEU Score",
    color: "hsl(var(--chart-1))",
  },
  cometScore: {
    label: "COMET Score",
    color: "hsl(var(--chart-2))",
  },
  metricXScore: {
    label: "MetricX Score",
    color: "hsl(var(--chart-3))",
  },
  terScore: {
    label: "TER Score",
    color: "hsl(var(--chart-4))",
  },
} satisfies ChartConfig;

// NEW: Multi-metric chart configuration for model performance
const multiMetricChartConfig = {
  avgBleu: {
    label: "BLEU Score (%)",
    color: "hsl(var(--chart-1))",
  },
  avgComet: {
    label: "COMET Score (%)",
    color: "hsl(var(--chart-2))",
  },
  avgTer: {
    label: "TER Score (%)",
    color: "hsl(var(--chart-3))",
  },
} satisfies ChartConfig;

const postEditChartConfig = {
  avgBleu: {
    label: "BLEU Score",
    color: "hsl(var(--chart-1))",
  },
  avgComet: {
    label: "COMET Score",
    color: "hsl(var(--chart-2))",
  },
  avgTer: {
    label: "TER Score",
    color: "hsl(var(--chart-3))",
  },
} satisfies ChartConfig;

const preferenceChartConfig = {
  selections: {
    label: "Selections",
    color: "hsl(var(--chart-1))",
  },
  avgRating: {
    label: "Avg Rating",
    color: "hsl(var(--chart-2))",
  },
} satisfies ChartConfig;

const processingChartConfig = {
  avgProcessingTime: {
    label: "Processing Time (ms)",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const severityChartConfig = {
  count: {
    label: "Count",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const errorHeatmapChartConfig = {
  painIndex: {
    label: "Pain Index",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const correlationChartConfig = {
  correlation: {
    label: "Correlation",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const utilizationChartConfig = {
  utilizationRate: {
    label: "Utilization Rate (%)",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const tmImpactChartConfig = {
  avgQualityScore: {
    label: "Quality Score",
    color: "hsl(var(--chart-1))",
  },
  timeSaved: {
    label: "Time Saved (min)",
    color: "hsl(var(--chart-2))",
  },
} satisfies ChartConfig;

// Translator Impact Components
const TranslationComparison: React.FC<{
  originalMT: string;
  humanEdited: string;
  sourceText: string;
  compact?: boolean;
}> = ({ originalMT, humanEdited, sourceText, compact = false }) => {
  const diffConfig = {
    splitView: !compact,
    showDiffOnly: false,
    hideLineNumbers: compact,
    useDarkTheme: false,
    leftTitle: 'Machine Translation',
    rightTitle: 'Human Edited',
  };

  return (
    <div className="space-y-4">
      <div className="p-3 bg-muted rounded-lg">
        <p className="text-sm font-medium text-muted-foreground">Source Text</p>
        <p className="text-sm">{sourceText}</p>
      </div>
      <div className="border rounded-lg overflow-hidden">
        <ReactDiffViewer
          oldValue={originalMT}
          newValue={humanEdited}
          {...diffConfig}
        />
      </div>
    </div>
  );
};

// Model Performance Controls Component
const ModelPerformanceControls: React.FC<{
  chartGroupBy: 'model' | 'language_pair';
  setChartGroupBy: (value: 'model' | 'language_pair') => void;
  selectedLanguagePair: string;
  setSelectedLanguagePair: (value: string) => void;
  onRefresh: () => void;
}> = ({ chartGroupBy, setChartGroupBy, selectedLanguagePair, setSelectedLanguagePair, onRefresh }) => (
  <div className="flex items-center space-x-4 mb-4">
    <div className="flex items-center space-x-2">
      <label className="text-sm font-medium">Group by:</label>
      <Select value={chartGroupBy} onValueChange={setChartGroupBy}>
        <SelectTrigger className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="model">Model</SelectItem>
          <SelectItem value="language_pair">Language Pair</SelectItem>
        </SelectContent>
      </Select>
    </div>
    
    <div className="flex items-center space-x-2">
      <label className="text-sm font-medium">Language Pair:</label>
      <Select value={selectedLanguagePair} onValueChange={setSelectedLanguagePair}>
        <SelectTrigger className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Pairs</SelectItem>
          <SelectItem value="JP-EN">Japanese → English</SelectItem>
          <SelectItem value="EN-JP">English → Japanese</SelectItem>
          <SelectItem value="FR-EN">French → English</SelectItem>
          <SelectItem value="EN-FR">English → French</SelectItem>
          <SelectItem value="JP-FR">Japanese → French</SelectItem>
        </SelectContent>
      </Select>
    </div>
    
    <Button onClick={onRefresh} variant="outline" size="sm">
      <RefreshCw className="h-4 w-4 mr-2" />
      Update Chart
    </Button>
  </div>
);

// Multi-Metric Chart Component
const MultiMetricChart: React.FC<{ data: ModelLeaderboardEntry[] }> = ({ data }) => {
  // Transform data to use the correct field names
  const chartData = data.map(item => ({
    name: item.name || item.model,
    avgBleu: item.avgBleu,
    avgComet: item.avgComet,
    avgTer: item.avgTer,
    totalTranslations: item.totalTranslations
  }));

  return (
    <ChartContainer config={multiMetricChartConfig} className="h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="name" 
            angle={-45}
            textAnchor="end"
            height={100}
            interval={0}
          />
          <YAxis domain={[0, 100]} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="avgBleu" fill="var(--color-avgBleu)" name="BLEU Score (%)" />
          <Bar dataKey="avgComet" fill="var(--color-avgComet)" name="COMET Score (%)" />
          <Bar dataKey="avgTer" fill="var(--color-avgTer)" name="TER Score (%)" />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
};

const QualityDashboard: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [postEditData, setPostEditData] = useState<PostEditMetricsData | null>(null);
  const [translatorImpactData, setTranslatorImpactData] = useState<TranslatorImpactData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedComparison, setSelectedComparison] = useState<TranslationComparisonEntry | null>(null);
  const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false);

  // State for chart controls
  const [chartGroupBy, setChartGroupBy] = useState<'model' | 'language_pair'>('model');
  const [selectedLanguagePair, setSelectedLanguagePair] = useState<string>('all');
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});

  // Move the useMemo calculation outside conditional rendering
  const editTypeChartData = useMemo(() => {
    if (!translatorImpactData || !translatorImpactData.comparisons || translatorImpactData.comparisons.length === 0) {
      return [];
    }
    const editTypeCounts = translatorImpactData.comparisons.reduce((acc, item) => {
      acc[item.editType] = (acc[item.editType] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    return Object.entries(editTypeCounts).map(([type, count]) => ({
      editType: type,
      count
    }));
  }, [translatorImpactData]);


  // Enhanced fetchDashboardData with new parameters
  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        group_by: chartGroupBy,
        ...(selectedLanguagePair !== 'all' && { language_pair: selectedLanguagePair }),
        ...(dateRange?.from && { date_from: dateRange.from }),
        ...(dateRange?.to && { date_to: dateRange.to })
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/analytics?${params}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setDashboardData(data);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchPostEditData = async () => {
    try {
      const params = new URLSearchParams({
        ...(selectedLanguagePair !== 'all' && { language_pair: selectedLanguagePair }),
        ...(dateRange?.from && { date_from: dateRange.from }),
        ...(dateRange?.to && { date_to: dateRange.to })
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/post-edit-metrics?${params}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setPostEditData(data);
    } catch (err) {
      console.error('Failed to fetch post-edit data:', err);
    }
  };

  const fetchTranslatorImpactData = async () => {
    try {
      const params = new URLSearchParams({
        ...(selectedLanguagePair !== 'all' && { language_pair: selectedLanguagePair })
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/translator-impact?${params}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setTranslatorImpactData(data);
    } catch (err) {
      console.error('Failed to fetch translator impact data:', err);
    }
  };

  // useEffect with new dependencies
  useEffect(() => {
    fetchDashboardData();
    fetchPostEditData();
    fetchTranslatorImpactData();
  }, [chartGroupBy, selectedLanguagePair, dateRange]);

  const getEditTypeBadge = (editType: string) => {
    const variants = {
      minor: 'default',
      moderate: 'secondary',
      major: 'destructive'
    } as const;
    
    return <Badge variant={variants[editType as keyof typeof variants] || 'outline'}>{editType}</Badge>;
  };

  const getSeverityBadge = (severity: string) => {
    const variants = {
      LOW: 'default',
      MEDIUM: 'secondary',
      HIGH: 'destructive',
      CRITICAL: 'destructive'
    } as const;
    
    return <Badge variant={variants[severity as keyof typeof variants] || 'outline'}>{severity}</Badge>;
  };

  const handleComparisonClick = (comparison: TranslationComparisonEntry) => {
    setSelectedComparison(comparison);
    setIsComparisonModalOpen(true);
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatTime = (timeMs: number) => {
    return `${timeMs.toFixed(0)}ms`;
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
            <p>Loading dashboard data...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              <p className="text-red-800">{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="pt-6">
            <p>No data available</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Quality Dashboard</h1>
        <div className="flex space-x-2">
          <Button onClick={fetchDashboardData} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      <Tabs defaultValue="performance" className="space-y-6">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="annotations">Annotations</TabsTrigger>
          <TabsTrigger value="multi-engine">Multi-Engine</TabsTrigger>
          <TabsTrigger value="quality-scores">Quality Scores</TabsTrigger>
          <TabsTrigger value="operational">Operational</TabsTrigger>
          <TabsTrigger value="translator-impact">Translator Impact</TabsTrigger>
        </TabsList>

        {/* UPDATED: Performance Tab with new functionality */}
        <TabsContent value="performance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Model Performance Comparison</CardTitle>
              <CardDescription>
                Compare TER, BLEU, and COMET scores across models or language pairs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModelPerformanceControls
                chartGroupBy={chartGroupBy}
                setChartGroupBy={setChartGroupBy}
                selectedLanguagePair={selectedLanguagePair}
                setSelectedLanguagePair={setSelectedLanguagePair}
                onRefresh={fetchDashboardData}
              />
              
              {dashboardData.modelPerformance.leaderboard.length > 0 ? (
                <MultiMetricChart data={dashboardData.modelPerformance.leaderboard} />
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No performance data available for the selected criteria
                </div>
              )}
            </CardContent>
          </Card>

          {/* Performance Over Time */}
          {dashboardData.modelPerformance.performanceOverTime.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Performance Trends Over Time</CardTitle>
                <CardDescription>Quality metrics trends across different time periods</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={performanceChartConfig} className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dashboardData.modelPerformance.performanceOverTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis domain={[0, 100]} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Area type="monotone" dataKey="bleuScore" stackId="1" stroke="var(--color-bleuScore)" fill="var(--color-bleuScore)" />
                      <Area type="monotone" dataKey="cometScore" stackId="1" stroke="var(--color-cometScore)" fill="var(--color-cometScore)" />
                      <Area type="monotone" dataKey="metricXScore" stackId="1" stroke="var(--color-metricXScore)" fill="var(--color-metricXScore)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}

          {/* Model Performance Leaderboard Table */}
          {dashboardData.modelPerformance.leaderboard.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Model Performance Leaderboard</CardTitle>
                <CardDescription>Detailed performance metrics by model</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Model</th>
                        <th className="p-3 text-left">Engine Type</th>
                        <th className="p-3 text-left">BLEU Score</th>
                        <th className="p-3 text-left">COMET Score</th>
                        <th className="p-3 text-left">TER Score</th>
                        <th className="p-3 text-left">MetricX Score</th>
                        <th className="p-3 text-left">Total Translations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.modelPerformance.leaderboard.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.name || item.model}</td>
                          <td className="p-3">{item.engineType}</td>
                          <td className="p-3">{formatPercentage(item.avgBleu / 100)}</td>
                          <td className="p-3">{formatPercentage(item.avgComet / 100)}</td>
                          <td className="p-3">{formatPercentage(item.avgTer / 100)}</td>
                          <td className="p-3">{item.avgMetricX.toFixed(2)}</td>
                          <td className="p-3">{item.totalTranslations}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Post-Edit Metrics */}
          {postEditData && (
            <Card>
              <CardHeader>
                <CardTitle>Post-Edit Quality Metrics</CardTitle>
                <CardDescription>
                  Quality metrics based on human post-editing ({postEditData.totalPostEdits} post-edits)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={postEditChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={postEditData.languagePairMetrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="languagePair" />
                      <YAxis domain={[0, 100]} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="avgBleu" fill="var(--color-avgBleu)" name="BLEU Score (%)" />
                      <Bar dataKey="avgComet" fill="var(--color-avgComet)" name="COMET Score (%)" />
                      <Bar dataKey="avgTer" fill="var(--color-avgTer)" name="TER Score (%)" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}

          {/* Correlation Matrix */}
          {postEditData && postEditData.correlationMatrix.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Metric Correlation Matrix</CardTitle>
                <CardDescription>Correlation between different quality metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {postEditData.correlationMatrix.map((item, index) => (
                    <div key={index} className="p-4 border rounded-lg text-center">
                      <div className="text-sm font-medium text-muted-foreground">
                        {item.metric1} vs {item.metric2}
                      </div>
                      <div className="text-2xl font-bold mt-2">
                        {item.correlation.toFixed(3)}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        p-value: {item.pValue.toFixed(3)}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Preferences Tab */}
        <TabsContent value="preferences" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Engine Preferences</CardTitle>
              <CardDescription>User preferences and ratings by engine type</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={preferenceChartConfig} className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.humanPreferences.enginePreferences.slice(0, 15)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="engine" angle={-45} textAnchor="end" height={100} />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="selectionCount" fill="var(--color-selections)" name="Selection Count" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Preference Reasons</CardTitle>
              <CardDescription>Why users prefer certain engines</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={preferenceChartConfig} className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.humanPreferences.preferenceReasons}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="reason" />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="count" fill="var(--color-selections)" name="Count" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          {/* Engine Preferences Table */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Engine Preferences</CardTitle>
              <CardDescription>Comprehensive breakdown of engine preferences by language pair</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="p-3 text-left">Engine</th>
                      <th className="p-3 text-left">Language Pair</th>
                      <th className="p-3 text-left">Selections</th>
                      <th className="p-3 text-left">Avg Rating</th>
                      <th className="p-3 text-left">Preference Reason</th>
                      <th className="p-3 text-left">Satisfaction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.humanPreferences.enginePreferences.slice(0, 20).map((item, index) => (
                      <tr key={index} className="border-b hover:bg-muted/30">
                        <td className="p-3 font-medium">{item.engine}</td>
                        <td className="p-3">{item.languagePair}</td>
                        <td className="p-3">{item.selectionCount}</td>
                        <td className="p-3">{item.avgRating.toFixed(2)}</td>
                        <td className="p-3">{item.preferenceReason}</td>
                        <td className="p-3">{item.overallSatisfaction.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Reviewer Behavior */}
          {dashboardData.humanPreferences.reviewerBehavior.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Reviewer Behavior Analysis</CardTitle>
                <CardDescription>Analysis of reviewer patterns and expertise levels</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {dashboardData.humanPreferences.reviewerBehavior.map((item, index) => (
                    <div key={index} className="p-4 border rounded-lg">
                      <div className="text-sm font-medium text-muted-foreground">
                        {item.reviewerExpertise}
                      </div>
                      <div className="mt-2 space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm">Avg Review Time:</span>
                          <span className="text-sm font-medium">{item.avgTimeToReview.toFixed(1)}min</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm">Cognitive Load:</span>
                          <span className="text-sm font-medium">{item.avgCognitiveLoad.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm">Approval Type:</span>
                          <span className="text-sm font-medium">{item.approvalType}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm">Count:</span>
                          <span className="text-sm font-medium">{item.count}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Annotations Tab */}
        <TabsContent value="annotations" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Error Severity Distribution</CardTitle>
              <CardDescription>Distribution of annotation severities across all models</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={severityChartConfig} className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.annotations.severityBreakdown}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="severity" />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="count" fill="var(--color-count)" name="Count">
                      <LabelList dataKey="count" position="top" />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Error Heatmap</CardTitle>
              <CardDescription>Error distribution by model and category</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {dashboardData.annotations.errorHeatmap.length > 0 ? (
                  <div className="rounded-md border">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-3 text-left">Model</th>
                          <th className="p-3 text-left">Category</th>
                          <th className="p-3 text-left">Error Type</th>
                          <th className="p-3 text-left">Severity</th>
                          <th className="p-3 text-left">Count</th>
                          <th className="p-3 text-left">Pain Index</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboardData.annotations.errorHeatmap.slice(0, 20).map((item, index) => (
                          <tr key={index} className="border-b hover:bg-muted/30">
                            <td className="p-3 font-medium">{item.model}</td>
                            <td className="p-3">{item.category}</td>
                            <td className="p-3">{item.errorType}</td>
                            <td className="p-3">{getSeverityBadge(item.severity)}</td>
                            <td className="p-3">{item.count}</td>
                            <td className="p-3 font-medium">{item.painIndex}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No error heatmap data available
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Pain Index Chart */}
          {dashboardData.annotations.errorHeatmap.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Pain Index by Model</CardTitle>
                <CardDescription>Aggregated pain index showing most problematic models</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={errorHeatmapChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.annotations.errorHeatmap.slice(0, 10)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="model" angle={-45} textAnchor="end" height={100} />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="painIndex" fill="var(--color-painIndex)" name="Pain Index" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}

          {/* Span Analysis */}
          {dashboardData.annotations.spanAnalysis.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Span Analysis</CardTitle>
                <CardDescription>Detailed analysis of annotation spans and suggested fixes</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {dashboardData.annotations.spanAnalysis.slice(0, 10).map((item, index) => (
                    <div key={index} className="p-4 border rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        <div className="text-sm font-medium">Span ID: {item.id}</div>
                        <Badge variant="outline">{item.category}</Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Source Span:</span>
                          <span className="ml-2">{item.sourceSpan.start}-{item.sourceSpan.end}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Target Span:</span>
                          <span className="ml-2">{item.targetSpan.start}-{item.targetSpan.end}</span>
                        </div>
                      </div>
                      <div className="mt-2">
                        <div className="text-sm text-muted-foreground">Suggested Fix:</div>
                        <div className="text-sm mt-1">{item.suggestedFix}</div>
                      </div>
                      <div className="mt-2 flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Confidence:</span>
                        <span className="text-sm font-medium">{formatPercentage(item.confidence)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Multi-Engine Tab */}
        <TabsContent value="multi-engine" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Multi-Engine Selection Trends</CardTitle>
              <CardDescription>Selection trends data visualization</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.multiEngine.selectionTrends.length > 0 ? (
                <ChartContainer config={performanceChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dashboardData.multiEngine.selectionTrends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Area type="monotone" dataKey="count" stroke="var(--color-bleuScore)" fill="var(--color-bleuScore)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No multi-engine selection data available
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pivot Quality Analysis</CardTitle>
              <CardDescription>Quality comparison between direct and pivot translations</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.multiEngine.pivotQuality.length > 0 ? (
                <ChartContainer config={performanceChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.multiEngine.pivotQuality}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="modelCombination" angle={-45} textAnchor="end" height={100} />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="directQuality" fill="var(--color-bleuScore)" name="Direct Quality" />
                      <Bar dataKey="pivotQuality" fill="var(--color-cometScore)" name="Pivot Quality" />
                      <Bar dataKey="intermediateQuality" fill="var(--color-metricXScore)" name="Intermediate Quality" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No pivot quality data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Inter-Rater Agreement */}
          {dashboardData.multiEngine.interRaterAgreement.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Inter-Rater Agreement</CardTitle>
                <CardDescription>Agreement levels between different annotators</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboardData.multiEngine.interRaterAgreement.map((item, index) => (
                    <div key={index} className="p-4 border rounded-lg text-center">
                      <div className="text-sm font-medium text-muted-foreground">
                        {item.annotatorPair}
                      </div>
                      <div className="text-2xl font-bold mt-2">
                        {formatPercentage(item.agreement)}
                      </div>
                      <div className="text-sm text-muted-foreground mt-1">
                        {item.category}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Selection Trends Table */}
          {dashboardData.multiEngine.selectionTrends.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Selection Trends Details</CardTitle>
                <CardDescription>Detailed breakdown of multi-engine selection patterns</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Date</th>
                        <th className="p-3 text-left">Selection Method</th>
                        <th className="p-3 text-left">Model Combination</th>
                        <th className="p-3 text-left">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.multiEngine.selectionTrends.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3">{formatDate(item.date)}</td>
                          <td className="p-3">{item.selectionMethod}</td>
                          <td className="p-3">{item.modelCombination}</td>
                          <td className="p-3 font-medium">{item.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Quality Scores Tab */}
        <TabsContent value="quality-scores" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Evaluation Mode Comparison</CardTitle>
              <CardDescription>Evaluation mode comparison visualization</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.qualityScores.evaluationModes.length > 0 ? (
                <ChartContainer config={performanceChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.qualityScores.evaluationModes}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="mode" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="avgScore" fill="var(--color-cometScore)" name="Average Score" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No quality score data available
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Score Distribution</CardTitle>
              <CardDescription>Distribution of quality scores across different metrics</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.qualityScores.scoreDistribution.length > 0 ? (
                <ChartContainer config={performanceChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.qualityScores.scoreDistribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="scoreRange" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="count" fill="var(--color-metricXScore)" name="Count" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No score distribution data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Correlation Matrix */}
          {dashboardData.qualityScores.correlationMatrix.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Quality Metric Correlations</CardTitle>
                <CardDescription>Correlation analysis between different quality metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {dashboardData.qualityScores.correlationMatrix.map((item, index) => (
                    <div key={index} className="p-4 border rounded-lg text-center">
                      <div className="text-sm font-medium text-muted-foreground">
                        {item.metric1} vs {item.metric2}
                      </div>
                      <div className="text-2xl font-bold mt-2">
                        {item.correlation.toFixed(3)}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        p-value: {item.pValue.toFixed(3)}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Evaluation Modes Details */}
          {dashboardData.qualityScores.evaluationModes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Evaluation Mode Details</CardTitle>
                <CardDescription>Detailed breakdown of evaluation modes and their performance</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Mode</th>
                        <th className="p-3 text-left">Average Score</th>
                        <th className="p-3 text-left">Confidence</th>
                        <th className="p-3 text-left">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.qualityScores.evaluationModes.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.mode}</td>
                          <td className="p-3">{item.avgScore.toFixed(3)}</td>
                          <td className="p-3">{formatPercentage(item.confidence)}</td>
                          <td className="p-3">{item.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Operational Tab */}
        <TabsContent value="operational" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Processing Times</CardTitle>
              <CardDescription>Average processing times by model and engine type</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={processingChartConfig} className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.operational.processingTimes}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="model" angle={-45} textAnchor="end" height={100} />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="avgProcessingTime" fill="var(--color-avgProcessingTime)" name="Avg Processing Time (ms)" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
              <CardDescription>Model availability and performance status</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.operational.systemHealth.length > 0 ? (
                <div className="space-y-4">
                  <div className="rounded-md border">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-3 text-left">Model</th>
                          <th className="p-3 text-left">Status</th>
                          <th className="p-3 text-left">Last Used</th>
                          <th className="p-3 text-left">Total Translations</th>
                          <th className="p-3 text-left">Avg Processing Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboardData.operational.systemHealth.map((item, index) => (
                          <tr key={index} className="border-b hover:bg-muted/30">
                            <td className="p-3 font-medium flex items-center">
                              {/* Red/Green Lamp */}
                              <Circle
                                className={`h-3 w-3 mr-2 ${
                                  item.isActive ? 'text-green-500 fill-green-500' : 'text-red-500 fill-red-500'
                                }`}
                                fill="currentColor" // Ensures the circle is filled with the color
                              />
                              {item.model}
                            </td>
                            <td className="p-3">
                               {item.isActive ? 'Active' : 'Inactive'} {/* Show text status */}
                            </td>
                            <td className="p-3">{formatDate(item.lastUsed)}</td>
                            <td className="p-3">{item.totalTranslations}</td>
                            <td className="p-3">{formatTime(item.avgProcessingTime)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No system health data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model Utilization */}
          {dashboardData.operational.modelUtilization.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Model Utilization</CardTitle>
                <CardDescription>Model usage patterns and efficiency metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={utilizationChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.operational.modelUtilization}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="model" angle={-45} textAnchor="end" height={100} />
                      <YAxis domain={[0, 100]} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="utilizationRate" fill="var(--color-utilizationRate)" name="Utilization Rate (%)" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}

          {/* Processing Times Details */}
          <Card>
            <CardHeader>
              <CardTitle>Processing Time Details</CardTitle>
              <CardDescription>Detailed breakdown of processing times by model and word count</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="p-3 text-left">Model</th>
                      <th className="p-3 text-left">Engine Type</th>
                      <th className="p-3 text-left">Word Count Bucket</th>
                      <th className="p-3 text-left">Avg Processing Time</th>
                      <th className="p-3 text-left">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.operational.processingTimes.map((item, index) => (
                      <tr key={index} className="border-b hover:bg-muted/30">
                        <td className="p-3 font-medium">{item.model}</td>
                        <td className="p-3">{item.engineType}</td>
                        <td className="p-3">{item.wordCountBucket}</td>
                        <td className="p-3">{formatTime(item.avgProcessingTime)}</td>
                        <td className="p-3">{item.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Model Utilization Details */}
          {dashboardData.operational.modelUtilization.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Model Utilization Details</CardTitle>
                <CardDescription>Detailed breakdown of model usage patterns and efficiency</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Model</th>
                        <th className="p-3 text-left">Utilization Rate</th>
                        <th className="p-3 text-left">Idle Days</th>
                        <th className="p-3 text-left">Needs Update</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.operational.modelUtilization.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.model}</td>
                          <td className="p-3">{formatPercentage(item.utilizationRate / 100)}</td>
                          <td className="p-3">{item.idleDays} days</td>
                          <td className="p-3">
                            <Badge variant={item.needsUpdate ? 'destructive' : 'default'}>
                              {item.needsUpdate ? 'Update Required' : 'Up to Date'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Translator Impact Tab */}
        <TabsContent value="translator-impact" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Translator Impact Analysis</CardTitle>
              <CardDescription>
                Compare machine translations with human-edited versions to measure translator impact
              </CardDescription>
            </CardHeader>
            <CardContent>
              {translatorImpactData && translatorImpactData.comparisons.length > 0 ? (
                <div className="space-y-4">
                  <div className="rounded-md border">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-3 text-left">Source Text</th>
                          <th className="p-3 text-left">Language</th>
                          <th className="p-3 text-left">Job</th>
                          <th className="p-3 text-left">Edit Type</th>
                          <th className="p-3 text-left">Improvement</th>
                          <th className="p-3 text-left">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {translatorImpactData.comparisons.slice(0, 20).map((item) => (
                          <tr key={item.id} className="border-b hover:bg-muted/30">
                            <td className="p-3 max-w-xs truncate">{item.sourceText}</td>
                            <td className="p-3">{item.languagePair}</td>
                            <td className="p-3">{item.jobName}</td>
                            <td className="p-3">{getEditTypeBadge(item.editType)}</td>
                            <td className="p-3">+{(item.improvementScore * 100).toFixed(1)}%</td>
                            <td className="p-3">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleComparisonClick(item)}
                              >
                                View Diff
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No translator impact data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Translator Summary */}
          {translatorImpactData && translatorImpactData.summary.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Translator Summary</CardTitle>
                <CardDescription>Summary statistics by translator</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Translator ID</th>
                        <th className="p-3 text-left">Total Edits</th>
                        <th className="p-3 text-left">Avg Improvement</th>
                        <th className="p-3 text-left">Avg Edit Distance</th>
                        <th className="p-3 text-left">Language Pairs</th>
                        <th className="p-3 text-left">Edit Distribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {translatorImpactData.summary.map((item) => (
                        <tr key={item.translatorId} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.translatorId}</td>
                          <td className="p-3">{item.totalEdits}</td>
                          <td className="p-3">+{(item.avgImprovementScore * 100).toFixed(1)}%</td>
                          <td className="p-3">{item.avgEditDistance.toFixed(1)}</td>
                          <td className="p-3">{item.languagePairs.join(', ')}</td>
                          <td className="p-3">
                            <div className="flex space-x-1">
                              <Badge variant="default">{item.editTypes.minor} minor</Badge>
                              <Badge variant="secondary">{item.editTypes.moderate} moderate</Badge>
                              <Badge variant="destructive">{item.editTypes.major} major</Badge>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Translation Impact Chart */}
          {editTypeChartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Translation Impact by Edit Type</CardTitle>
                <CardDescription>Distribution of edit types and their impact on quality</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={preferenceChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={editTypeChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="editType" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="count" fill="var(--color-selections)" name="Count" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}
          {editTypeChartData.length === 0 && (
            <Card>
              <CardContent className="text-center py-8 text-muted-foreground">
                No translation impact chart data available
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* TM & Glossary Tab */}
        <TabsContent value="tm-glossary" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Translation Memory Impact</CardTitle>
              <CardDescription>Impact of translation memory matches on quality and efficiency</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboardData.tmGlossary.tmImpact.length > 0 ? (
                <ChartContainer config={tmImpactChartConfig} className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.tmGlossary.tmImpact}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="matchPercentage" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="avgQualityScore" fill="var(--color-avgQualityScore)" name="Quality Score" />
                      <Bar dataKey="timeSaved" fill="var(--color-timeSaved)" name="Time Saved (min)" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No translation memory impact data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Glossary Usage */}
          {dashboardData.tmGlossary.glossaryUsage.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Glossary Usage Analysis</CardTitle>
                <CardDescription>Analysis of glossary term usage and impact on translation quality</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Term</th>
                        <th className="p-3 text-left">Usage Count</th>
                        <th className="p-3 text-left">Override Rate</th>
                        <th className="p-3 text-left">Quality Impact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.tmGlossary.glossaryUsage.slice(0, 20).map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.term}</td>
                          <td className="p-3">{item.usageCount}</td>
                          <td className="p-3">{formatPercentage(item.overrideRate)}</td>
                          <td className="p-3">{item.qualityImpact.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Term Overrides */}
          {dashboardData.tmGlossary.termOverrides.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Term Override Analysis</CardTitle>
                <CardDescription>Analysis of glossary term overrides and their impact</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Term</th>
                        <th className="p-3 text-left">Original Translation</th>
                        <th className="p-3 text-left">Override Translation</th>
                        <th className="p-3 text-left">Frequency</th>
                        <th className="p-3 text-left">Quality Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.tmGlossary.termOverrides.slice(0, 15).map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.term}</td>
                          <td className="p-3 max-w-xs truncate">{item.originalTranslation}</td>
                          <td className="p-3 max-w-xs truncate">{item.overrideTranslation}</td>
                          <td className="p-3">{item.frequency}</td>
                          <td className="p-3">
                            <span className={item.qualityDelta >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {item.qualityDelta >= 0 ? '+' : ''}{item.qualityDelta.toFixed(2)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* TM Impact Details */}
          {dashboardData.tmGlossary.tmImpact.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Translation Memory Impact Details</CardTitle>
                <CardDescription>Detailed breakdown of TM match impact on quality and efficiency</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Match Percentage</th>
                        <th className="p-3 text-left">Avg Quality Score</th>
                        <th className="p-3 text-left">Time Saved (min)</th>
                        <th className="p-3 text-left">Approval Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.tmGlossary.tmImpact.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.matchPercentage}</td>
                          <td className="p-3">{item.avgQualityScore.toFixed(2)}</td>
                          <td className="p-3">{item.timeSaved.toFixed(1)}</td>
                          <td className="p-3">{formatPercentage(item.approvalRate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Comparison Modal */}
      <Dialog open={isComparisonModalOpen} onOpenChange={setIsComparisonModalOpen}>
        <DialogContent className="max-w-none w-auto h-auto">
          <DialogHeader>
            <DialogTitle>Translation Comparison</DialogTitle>
            <DialogDescription>
              Compare machine translation with human-edited version
            </DialogDescription>
          </DialogHeader>
          {selectedComparison && (
            <TranslationComparison
              originalMT={selectedComparison.originalMT}
              humanEdited={selectedComparison.humanEdited}
              sourceText={selectedComparison.sourceText}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QualityDashboard;