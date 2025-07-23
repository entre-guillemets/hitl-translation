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
import { Area, AreaChart, Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
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
import { Label } from '@/components/ui/label';


// API Configuration
const API_BASE_URL = 'http://localhost:8001';

// Language Options (for filters)
const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JP' },
  { label: 'French', value: 'FR' },
];

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
  avgTer: number; 
  avgChrf: number; // Added ChrF
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
  avgTer: number; 
  avgMetricX: number;
  avgChrf: number;  // Added ChrF
  totalTranslations: number;
  languagePairs?: string[];
  models?: string[];
  confidenceInterval: {
    bleuLow: number;
    bleuHigh: number;
    cometLow: number;
    cometHigh: number;
    chrfLow: number; // Added ChrF
    chrfHigh: number; // Added ChrF
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
  stackedPainIndexByErrorType: { [key: string]: any; model: string }[]; // Added for new chart
  totalMQMScore: number; // Added for MQM score
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

interface CorrelationEntry {
  metric1: string;
  metric2: string;
  correlation: number;
  pValue: number;
}

interface ScoreDistributionEntry {
  metric: string;
  scoreRange: string;
  scores: number[]; // Added scores property
  count?: number; // Optional, as scores array length can derive count
  percentage?: number; // Optional, as not always provided by backend
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
  avgChrf: {
    label: "ChrF Score (%)",
    color: "hsl(var(--chart-4))",
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
  avgChrf: { 
    label: "ChrF Score",
    color: "hsl(var(--chart-4))",
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
  count: { // Added for preference reasons chart
    label: "Count",
    color: "hsl(var(--chart-1))",
  }
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

// Custom colors for stacked bar chart by errorType
const errorTypeColors: { [key: string]: string } = {
  "Translation Error": "hsl(var(--chart-1))", // A distinct color
  "Fluency Error": "hsl(var(--chart-2))",    // Another distinct color
  "Accuracy Error": "hsl(var(--chart-3))",   // Another distinct color
  "Terminology Error": "hsl(var(--chart-4))",
  "Style Error": "hsl(var(--chart-5))",
  "Grammar Error": "hsl(var(--chart-6))",
  "Punctuation Error": "hsl(var(--chart-7))",
  "Omission": "hsl(var(--chart-8))",
  "Addition": "hsl(var(--chart-9))",
  "Uncategorized": "hsl(var(--chart-10))",
  "general": "hsl(var(--chart-11))", // Default if errorType is 'general'
  // Add more as needed based on your AnnotationCategory or specific error types
};

// Helper to get all unique error types for stacked bar chart keys
const getAllErrorTypes = (data: AnnotationData) => {
  const errorTypes = new Set<string>();
  data.errorHeatmap.forEach(item => {
    errorTypes.add(item.errorType);
  });
  return Array.from(errorTypes);
};

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
          {/* Dynamically populate based on available data or common pairs */}
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
    avgChrf: item.avgChrf, // Added ChrF
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
          <Bar dataKey="avgChrf" fill="var(--color-avgChrf)" name="ChrF Score (%)" /> {/* Added ChrF */}
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
};

// NEW: Metric Correlation Matrix Component
const MetricCorrelationMatrix: React.FC<{ data: CorrelationEntry[] }> = ({ data }) => {
  const metrics = useMemo(() => {
    const uniqueMetrics = new Set<string>();
    data.forEach(d => {
      uniqueMetrics.add(d.metric1);
      uniqueMetrics.add(d.metric2);
    });
    return Array.from(uniqueMetrics).sort(); // Sort to ensure consistent order
  }, [data]);

  const getCorrelationValue = (m1: string, m2: string) => {
    if (m1 === m2) return 1.00;
    const entry = data.find(d =>
      (d.metric1 === m1 && d.metric2 === m2) ||
      (d.metric1 === m2 && d.metric2 === m1)
    );
    return entry ? parseFloat(entry.correlation.toFixed(2)) : 0.00; // Return 0 if no correlation found
  };

  const getColor = (value: number) => {
    // Red for negative, Green for positive, White/Grey for near zero
    if (value > 0) {
      const intensity = value; // 0 to 1
      return `rgba(0, 128, 0, ${intensity})`; // Green
    } else if (value < 0) {
      const intensity = Math.abs(value); // 0 to 1
      return `rgba(255, 0, 0, ${intensity})`; // Red
    }
    return 'rgba(128, 128, 128, 0.5)'; // Grey for 0
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle>Quality Score Correlation Matrix</CardTitle>
        <CardDescription>
          Correlation between BLEU, COMET, TER, and ChrF scores. (Higher positive value = stronger positive correlation,
          higher negative value = stronger negative correlation).
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-grow flex items-center justify-center p-4">
        {data.length > 0 ? (
          <div className="grid gap-1" style={{
            gridTemplateColumns: `auto repeat(${metrics.length}, minmax(80px, 1fr))`,
            gridTemplateRows: `auto repeat(${metrics.length}, minmax(40px, 1fr))`
          }}>
            {/* Corner empty cell */}
            <div className="p-2"></div>
            {/* Column Headers */}
            {metrics.map(metric => (
              <div key={`col-${metric}`} className="p-2 font-bold text-center text-sm">
                {metric}
              </div>
            ))}
            {/* Rows */}
            {metrics.map(rowMetric => (
              <React.Fragment key={`row-${rowMetric}`}>
                <div className="p-2 font-bold text-right text-sm">
                  {rowMetric}
                </div>
                {metrics.map(colMetric => {
                  const correlation = getCorrelationValue(rowMetric, colMetric);
                  const isDiagonal = rowMetric === colMetric;
                  return (
                    <div
                      key={`${rowMetric}-${colMetric}`}
                      className="p-2 rounded-md flex items-center justify-center text-sm font-medium"
                      style={{
                        backgroundColor: isDiagonal ? 'hsl(var(--muted))' : getColor(correlation),
                        color: isDiagonal ? 'hsl(var(--muted-foreground))' : 'white', // Text color for contrast
                        border: '1px solid hsl(var(--border))'
                      }}
                    >
                      {correlation.toFixed(2)}
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No correlation data available for the selected criteria.
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// NEW: Error Heatmap Component
const ErrorHeatmapChart: React.FC<{ data: ErrorHeatmapEntry[] }> = ({ data }) => {
  const uniqueModels = useMemo(() => Array.from(new Set(data.map(d => d.model))).sort(), [data]);
  const uniqueErrorTypes = useMemo(() => Array.from(new Set(data.map(d => d.errorType))).sort(), [data]);

  const maxPainIndex = useMemo(() => Math.max(...data.map(d => d.painIndex)), [data]);
  const minPainIndex = useMemo(() => Math.min(...data.map(d => d.painIndex)), [data]);

  // Function to get color from red to green
  const getHeatmapColor = (painIndex: number) => {
    if (uniqueModels.length === 0 || uniqueErrorTypes.length === 0 || maxPainIndex === 0) {
        return 'rgba(128, 128, 128, 0.2)'; // Light grey for no data or zero max
    }

    // Normalize painIndex to a 0-1 scale
    const normalizedPain = (painIndex - minPainIndex) / (maxPainIndex - minPainIndex || 1);

    // Interpolate between red (high pain) and green (low pain)
    // For Red: hsl(0, 100%, 50%) -> (255,0,0)
    // For Green: hsl(120, 100%, 50%) -> (0,255,0)
    // We want red for higher pain, green for lower pain.
    // So, low pain (normalizedPain close to 0) should be green (hue 120)
    // High pain (normalizedPain close to 1) should be red (hue 0)
    const hue = (1 - normalizedPain) * 120; // 120 (green) to 0 (red)
    const lightness = 50 + normalizedPain * 10; // Slightly darker for higher pain for better visibility
    const saturation = 80 + normalizedPain * 20; // More saturated for higher pain
    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Error Heatmap by Model and Error Type</CardTitle>
        <CardDescription>Visual representation of error frequency and pain index.</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length > 0 ? (
          <div className="overflow-auto max-h-[500px]">
            <div className="grid gap-px bg-border p-px rounded-md" style={{
              gridTemplateColumns: `120px repeat(${uniqueErrorTypes.length}, minmax(100px, 1fr))`,
              gridAutoRows: 'minmax(40px, auto)'
            }}>
              {/* Corner empty cell */}
              <div className="bg-background"></div>
              {/* Error Type Headers (X-axis) */}
              {uniqueErrorTypes.map(errorType => (
                <div key={errorType} className="bg-muted p-2 text-center font-semibold text-xs border-b">
                  {errorType}
                </div>
              ))}
              {/* Model Rows (Y-axis) and Cells */}
              {uniqueModels.map(model => (
                <React.Fragment key={model}>
                  <div className="bg-muted p-2 font-semibold text-right text-xs border-r flex items-center justify-end pr-3">
                    {model}
                  </div>
                  {uniqueErrorTypes.map(errorType => {
                    const cellData = data.find(d => d.model === model && d.errorType === errorType);
                    const painIndex = cellData ? cellData.painIndex : 0;
                    const count = cellData ? cellData.count : 0;
                    const severity = cellData ? cellData.severity : 'N/A';

                    return (
                      <div
                        key={`${model}-${errorType}`}
                        className="p-2 flex items-center justify-center text-xs"
                        style={{ backgroundColor: getHeatmapColor(painIndex) }}
                      >
                        <Tooltip content={
                          <div className="bg-background text-foreground text-xs p-2 rounded-md shadow-lg border">
                            <div>Model: <span className="font-medium">{model}</span></div>
                            <div>Error Type: <span className="font-medium">{errorType}</span></div>
                            <div>Count: <span className="font-medium">{count}</span></div>
                            <div>Pain Index: <span className="font-medium">{painIndex.toFixed(0)}</span></div>
                            <div>Severity: <span className="font-medium">{severity}</span></div>
                          </div>
                        } />
                        <span className="text-foreground/90 font-medium">{painIndex > 0 ? painIndex.toFixed(0) : '-'}</span>
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No error heatmap data available for the selected criteria.
          </div>
        )}
      </CardContent>
    </Card>
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

  // Pagination states for Translator Impact Analysis
  const [currentPageTranslator, setCurrentPageTranslator] = useState(1);
  const [itemsPerPageTranslator, setItemsPerPageTranslator] = useState(25);
  const itemsPerPageOptionsTranslator = [25, 50, 100, 0]; // 0 for All

  // Filter states for Detailed Engine Preferences
  const [preferencesEngineFilter, setPreferencesEngineFilter] = useState<string>('all');
  const [preferencesLanguagePairFilter, setPreferencesLanguagePairFilter] = useState<string>('all');
  // Pagination states for Detailed Engine Preferences
  const [currentPagePreferences, setCurrentPagePreferences] = useState(1);
  const [itemsPerPagePreferences, setItemsPerPagePreferences] = useState(25);
  const itemsPerPageOptionsPreferences = [25, 50, 100, 0];


  // Memoized data for Translator Impact Analysis table pagination
  const paginatedTranslatorComparisons = useMemo(() => {
    if (!translatorImpactData || !translatorImpactData.comparisons) return [];
    const startIndex = (currentPageTranslator - 1) * itemsPerPageTranslator;
    const endIndex = itemsPerPageTranslator === 0 ? translatorImpactData.comparisons.length : startIndex + itemsPerPageTranslator;
    return translatorImpactData.comparisons.slice(startIndex, endIndex);
  }, [translatorImpactData, currentPageTranslator, itemsPerPageTranslator]);

  const totalTranslatorComparisonsCount = translatorImpactData?.comparisons?.length || 0;
  const totalPagesTranslator = itemsPerPageTranslator === 0
    ? 1
    : Math.ceil(totalTranslatorComparisonsCount / itemsPerPageTranslator);

  // Memoized data for Detailed Engine Preferences table pagination and filters
  const filteredEnginePreferences = useMemo(() => {
    let filtered = dashboardData?.humanPreferences.enginePreferences || [];

    if (preferencesEngineFilter !== 'all') {
      filtered = filtered.filter(pref => pref.engine === preferencesEngineFilter);
    }
    if (preferencesLanguagePairFilter !== 'all') {
      filtered = filtered.filter(pref => pref.languagePair === preferencesLanguagePairFilter);
    }
    return filtered;
  }, [dashboardData?.humanPreferences.enginePreferences, preferencesEngineFilter, preferencesLanguagePairFilter]);

  const paginatedEnginePreferences = useMemo(() => {
    const startIndex = (currentPagePreferences - 1) * itemsPerPagePreferences;
    const endIndex = itemsPerPagePreferences === 0 ? filteredEnginePreferences.length : startIndex + itemsPerPagePreferences;
    return filteredEnginePreferences.slice(startIndex, endIndex);
  }, [filteredEnginePreferences, currentPagePreferences, itemsPerPagePreferences]);

  const totalFilteredPreferencesCount = filteredEnginePreferences.length;
  const totalPagesPreferences = itemsPerPagePreferences === 0
    ? 1
    : Math.ceil(totalFilteredPreferencesCount / itemsPerPagePreferences);


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

  const allErrorTypesForStackedChart = useMemo(() => {
    if (!dashboardData?.annotations.stackedPainIndexByErrorType) return [];
    const uniqueTypes = new Set<string>();
    dashboardData.annotations.stackedPainIndexByErrorType.forEach(item => {
      Object.keys(item).forEach(key => {
        if (key !== 'model') {
          uniqueTypes.add(key);
        }
      });
    });
    return Array.from(uniqueTypes);
  }, [dashboardData?.annotations.stackedPainIndexByErrorType]);

  const getLanguageLabel = (code: string) => {
    return languageOptions.find((lang: { value: string }) => lang.value === code)?.label || code;
  };

  // Enhanced fetchDashboardData with new parameters
  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        group_by: chartGroupBy,
        ...(selectedLanguagePair !== 'all' && { language_pair: selectedLanguagePair }),
        ...(preferencesEngineFilter !== 'all' && { engine_filter: preferencesEngineFilter }), // Pass engine filter
        ...(preferencesLanguagePairFilter !== 'all' && { language_pair: preferencesLanguagePairFilter }), // Pass language pair filter for preferences
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

  // REMOVED individual fetch calls for multi-engine, quality-scores, and tm-glossary
  // as their data is expected to be part of the main dashboardData payload.
  // The 'multiEngine', 'qualityScores', and 'tmGlossary' data will be accessed directly from dashboardData.
  /*
  const fetchMultiEngineData = async () => { ... };
  const fetchQualityScoresData = async () => { ... };
  const fetchTMGlossaryData = async () => { ... };
  */

  // useEffect with updated dependencies and removed specific fetches
  useEffect(() => {
    fetchDashboardData();
    fetchPostEditData();
    fetchTranslatorImpactData();
    // Removed these calls:
    // fetchMultiEngineData();
    // fetchQualityScoresData();
    // fetchTMGlossaryData();
  }, [
    chartGroupBy,
    selectedLanguagePair,
    dateRange,
    preferencesEngineFilter,
    preferencesLanguagePairFilter
  ]);

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
    return `${(value).toFixed(1)}%`; // Assuming values are already 0-100
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatTime = (timeMs: number) => {
    return `${timeMs.toFixed(0)}ms`;
  };

  // Helper for average of scores list for Quality Scores -> Score Distribution
  const calculateAverage = (scores: number[] | undefined) => {
    if (!scores || scores.length === 0) return 0;
    return (scores.reduce((sum, current) => sum + current, 0) / scores.length).toFixed(1);
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

      <Tabs defaultValue="quality" className="space-y-6">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="translator-impact">Translator Impact</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="annotations">Annotations</TabsTrigger>
          <TabsTrigger value="operational">Operational</TabsTrigger>
          <TabsTrigger value="tm-glossary">TM & Glossary</TabsTrigger>
          {/* Note: Multi-Engine tab is intentionally excluded as per recent discussions, 
             assuming its content is integrated elsewhere or no longer needed as a separate top-level tab.
             If it's needed, it must be added here and its content (further down) uncommented.
             If it's to be a top-level tab, you'd need to add:
             <TabsTrigger value="multi-engine">Multi-Engine</TabsTrigger>
             And then ensure dashboardData.multiEngine is directly used.
             Given current issue, I'm removing the old API calls that were causing 404s.
          */}
        </TabsList>

        {/* NEW: Quality Tab */}
        <TabsContent value="quality" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              {/* Post-Edit Metrics */}
              {postEditData && (
                <Card className="h-full">
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
                          <Bar dataKey="avgChrf" fill="var(--color-avgChrf)" name="ChrF Score (%)" />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartContainer>
                  </CardContent>
                </Card>
              )}
            </div>
            <div className="lg:col-span-1">
              {/* Correlation Matrix */}
              {postEditData && postEditData.correlationMatrix.length > 0 && (
                <MetricCorrelationMatrix data={postEditData.correlationMatrix} />
              )}
            </div>
          </div>
          
          {/* Quality Scores - Evaluation Modes & Score Distribution */}
          <Card>
              <CardHeader>
                  <CardTitle>Quality Score Evaluation Modes</CardTitle>
                  <CardDescription>Overview of different evaluation modes and their average scores.</CardDescription>
              </CardHeader>
              <CardContent>
                  {dashboardData.qualityScores.evaluationModes.length > 0 ? (
                      <div className="rounded-md border">
                          <table className="w-full">
                              <thead>
                                  <tr className="border-b bg-muted/50">
                                      <th className="p-3 text-left">Mode</th>
                                      <th className="p-3 text-left">Count</th>
                                      <th className="p-3 text-left">Average Score</th>
                                      <th className="p-3 text-left">Confidence</th>
                                  </tr>
                              </thead>
                              <tbody>
                                  {dashboardData.qualityScores.evaluationModes.map((item, index) => (
                                      <tr key={index} className="border-b hover:bg-muted/30">
                                          <td className="p-3 font-medium">{item.mode}</td>
                                          <td className="p-3">{item.count}</td>
                                          <td className="p-3">{item.avgScore.toFixed(2)}</td>
                                          <td className="p-3">{formatPercentage(item.confidence * 100)}</td>
                                      </tr>
                                  ))}
                              </tbody>
                          </table>
                      </div>
                  ) : (
                      <div className="text-center py-8 text-muted-foreground">
                          No evaluation modes data available.
                      </div>
                  )}
              </CardContent>
          </Card>

          <Card>
              <CardHeader>
                  <CardTitle>Quality Score Distribution</CardTitle>
                  <CardDescription>Distribution of scores for different metrics.</CardDescription>
              </CardHeader>
              <CardContent>
                  {dashboardData.qualityScores.scoreDistribution.length > 0 ? (
                      <div className="space-y-4">
                          {dashboardData.qualityScores.scoreDistribution.map((item, index) => (
                              <div key={index} className="p-4 border rounded-lg">
                                  <div className="text-sm font-medium text-muted-foreground mb-2">
                                      {item.metric} (Range: {item.scoreRange})
                                  </div>
                                  <div className="flex justify-between items-center">
                                      <span className="text-sm">Total Entries:</span>
                                      <span className="text-sm font-medium">{item.scores.length}</span>
                                  </div>
                                  <div className="flex justify-between items-center">
                                      <span className="text-sm">Average Score:</span>
                                      <span className="text-sm font-medium">{calculateAverage(item.scores)}</span>
                                  </div>
                                  {/* You can add a histogram/chart here for distribution if desired */}
                              </div>
                          ))}
                      </div>
                  ) : (
                      <div className="text-center py-8 text-muted-foreground">
                          No score distribution data available.
                      </div>
                  )}
              </CardContent>
          </Card>
        </TabsContent>


        {/* UPDATED: Performance Tab with new functionality */}
        <TabsContent value="performance" className="space-y-6">
          {/* Model Performance Comparison with filters */}
          <Card>
            <CardHeader>
              <CardTitle>Model Performance Comparison</CardTitle>
              <CardDescription>
                Compare TER, BLEU, COMET, and ChrF scores across models or language pairs (based on human post-edits)
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
                  No performance data available for the selected criteria. Ensure there are human post-edits.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model Performance Leaderboard Table */}
          {dashboardData.modelPerformance.leaderboard.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Model Performance Leaderboard</CardTitle>
                <CardDescription>Detailed performance metrics by model (based on human post-edits)</CardDescription>
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
                        <th className="p-3 text-left">ChrF Score</th> {/* Added ChrF */}
                        <th className="p-3 text-left">Total Translations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.modelPerformance.leaderboard.map((item, index) => (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.name || item.model}</td>
                          <td className="p-3">{item.engineType}</td>
                          <td className="p-3">{formatPercentage(item.avgBleu)}</td>
                          <td className="p-3">{formatPercentage(item.avgComet)}</td>
                          <td className="p-3">{formatPercentage(item.avgTer)}</td>
                          <td className="p-3">{formatPercentage(item.avgChrf)}</td> {/* Added ChrF */}
                          <td className="p-3">{item.totalTranslations}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Performance Over Time - Kept for completeness, though not explicitly requested in new order */}
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
        </TabsContent>

        {/* Translator Impact Tab (moved here) */}
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
                        {paginatedTranslatorComparisons.map((item) => ( // Use paginated data
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
                  {/* Pagination controls for Translator Impact Analysis */}
                  <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
                    <span>Showing {paginatedTranslatorComparisons.length} of {totalTranslatorComparisonsCount} entries</span>
                    <div className="flex items-center space-x-2">
                      <Label htmlFor="items-per-page-translator" className="text-sm font-medium">Items per page:</Label>
                      <Select
                        value={String(itemsPerPageTranslator)}
                        onValueChange={(value: string) => {
                          setItemsPerPageTranslator(Number(value));
                          setCurrentPageTranslator(1);
                        }}
                      >
                        <SelectTrigger className="w-[100px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {itemsPerPageOptionsTranslator.map((option, index) => (
                            <SelectItem key={index} value={String(option)}>
                              {option === 0 ? 'All' : option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPageTranslator(prev => Math.max(1, prev - 1))}
                        disabled={currentPageTranslator === 1}
                      >
                        Previous
                      </Button>
                      <span className="text-sm">Page {currentPageTranslator} of {totalPagesTranslator}</span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPageTranslator(prev => Math.min(totalPagesTranslator, prev + 1))}
                        disabled={currentPageTranslator === totalPagesTranslator || totalPagesTranslator === 0}
                      >
                        Next
                      </Button>
                    </div>
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
                    <Bar dataKey="count" fill="var(--color-count)" name="Count" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          {/* Detailed Engine Preferences Table with Filters and Pagination */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Engine Preferences</CardTitle>
              <CardDescription>Comprehensive breakdown of engine preferences by language pair</CardDescription>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                <div>
                  <Label className="text-sm font-medium">Filter by Engine</Label>
                  <Select value={preferencesEngineFilter} onValueChange={setPreferencesEngineFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Engines" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Engines</SelectItem>
                      {/* Dynamically populate available engines */}
                      {Array.from(new Set(dashboardData.humanPreferences.enginePreferences.map(p => p.engine))).map(engine => (
                        <SelectItem key={engine} value={engine}>{engine}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-medium">Filter by Language Pair</Label>
                  <Select value={preferencesLanguagePairFilter} onValueChange={setPreferencesLanguagePairFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Language Pairs" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Language Pairs</SelectItem>
                      {/* Dynamically populate available language pairs */}
                      {Array.from(new Set(dashboardData.humanPreferences.enginePreferences.map(p => p.languagePair))).map(pair => (
                        <SelectItem key={pair} value={pair}>{pair}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
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
                    {paginatedEnginePreferences.map((item, index) => (
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
              {/* Pagination controls for Detailed Engine Preferences */}
              <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
                <span>Showing {paginatedEnginePreferences.length} of {totalFilteredPreferencesCount} entries</span>
                <div className="flex items-center space-x-2">
                  <Label htmlFor="items-per-page-preferences" className="text-sm font-medium">Items per page:</Label>
                  <Select
                    value={String(itemsPerPagePreferences)}
                    onValueChange={(value: string) => {
                      setItemsPerPagePreferences(Number(value));
                      setCurrentPagePreferences(1);
                    }}
                  >
                    <SelectTrigger className="w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {itemsPerPageOptionsPreferences.map((option, index) => (
                        <SelectItem key={index} value={String(option)}>
                          {option === 0 ? 'All' : option}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPagePreferences(prev => Math.max(1, prev - 1))}
                    disabled={currentPagePreferences === 1}
                  >
                    Previous
                  </Button>
                  <span className="text-sm">Page {currentPagePreferences} of {totalPagesPreferences}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPagePreferences(prev => Math.min(totalPagesPreferences, prev + 1))}
                    disabled={currentPagePreferences === totalPagesPreferences || totalPagesPreferences === 0}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Reviewer Behavior - Kept for completeness, not explicitly moved */}
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
          {/* NEW: Error Heatmap Chart */}
          {dashboardData.annotations.errorHeatmap.length > 0 ? (
            <ErrorHeatmapChart data={dashboardData.annotations.errorHeatmap} />
          ) : (
            <Card>
              <CardContent className="text-center py-8 text-muted-foreground">
                No error heatmap data available
              </CardContent>
            </Card>
          )}

          {/* NEW: Pain Index by Model (Stacked Bar Chart by errorType) */}
          {dashboardData.annotations.stackedPainIndexByErrorType.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Pain Index by Model (by Error Type)</CardTitle>
                <CardDescription>Aggregated pain index showing most problematic models, broken down by error type.</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={errorHeatmapChartConfig} className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData.annotations.stackedPainIndexByErrorType} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="model"
                        angle={-45}
                        textAnchor="end"
                        height={100}
                        interval={0}
                      />
                      <YAxis label={{ value: 'Pain Index', angle: -90, position: 'insideLeft' }} />
                      <Tooltip cursor={{ fill: 'transparent' }} content={<ChartTooltipContent />} />
                      <Legend verticalAlign="top" height={36} />
                      {allErrorTypesForStackedChart.map((type, index) => (
                        <Bar
                          key={type}
                          dataKey={type}
                          stackId="a"
                          fill={errorTypeColors[type] || `hsl(var(--chart-${(index % 12) + 1}))`} // Fallback colors
                          name={type}
                        >
                          <LabelList dataKey={type} position="insideTop" />
                        </Bar>
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          )}
          
          {/* Total MQM Score (New Card) */}
          <Card>
            <CardHeader>
              <CardTitle>Total MQM Score</CardTitle>
              <CardDescription>
                Overall Quality Estimation Score (Lower is better, weighted errors per string)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center p-4">
                <span className="text-5xl font-bold text-primary">
                  {dashboardData.annotations.totalMQMScore.toFixed(2)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Original Severity Distribution - kept for completeness */}
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

          {/* Span Analysis - Kept for completeness */}
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
                          <td className="p-3">{formatPercentage(item.utilizationRate)}</td>
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

        {/* TM & Glossary Tab (Restored) */}
        <TabsContent value="tm-glossary" className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Translation Memory (TM) Impact</CardTitle>
                    <CardDescription>Analysis of TM match percentages on quality and time saved.</CardDescription>
                </CardHeader>
                <CardContent>
                    {dashboardData.tmGlossary.tmImpact.length > 0 ? (
                        <ChartContainer config={tmImpactChartConfig} className="h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={dashboardData.tmGlossary.tmImpact}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="matchPercentage" />
                                    <YAxis yAxisId="left" orientation="left" stroke="var(--color-avgQualityScore)" />
                                    <YAxis yAxisId="right" orientation="right" stroke="var(--color-timeSaved)" />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <Legend />
                                    <Bar yAxisId="left" dataKey="avgQualityScore" fill="var(--color-avgQualityScore)" name="Avg Quality Score" />
                                    <Bar yAxisId="right" dataKey="timeSaved" fill="var(--color-timeSaved)" name="Time Saved (min)" />
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartContainer>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No TM impact data available.
                        </div>
                    )}
                    {dashboardData.tmGlossary.tmImpact.length > 0 && (
                        <div className="rounded-md border mt-4">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b bg-muted/50">
                                        <th className="p-3 text-left">Match %</th>
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
                                            <td className="p-3">{item.timeSaved.toFixed(0)}</td>
                                            <td className="p-3">{formatPercentage(item.approvalRate * 100)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Glossary Usage</CardTitle>
                    <CardDescription>Most frequently used glossary terms and their impact.</CardDescription>
                </CardHeader>
                <CardContent>
                    {dashboardData.tmGlossary.glossaryUsage.length > 0 ? (
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
                                    {dashboardData.tmGlossary.glossaryUsage.map((item, index) => (
                                        <tr key={index} className="border-b hover:bg-muted/30">
                                            <td className="p-3 font-medium">{item.term}</td>
                                            <td className="p-3">{item.usageCount}</td>
                                            <td className="p-3">{formatPercentage(item.overrideRate * 100)}</td>
                                            <td className="p-3">{item.qualityImpact.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No glossary usage data available.
                        </div>
                    )}
                </CardContent>
            </Card>
            {/* Term Overrides if data is available and you want to display it */}
            {dashboardData.tmGlossary.termOverrides.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Term Overrides</CardTitle>
                        <CardDescription>Analysis of frequently overridden glossary terms.</CardDescription>
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
                                    {dashboardData.tmGlossary.termOverrides.map((item, index) => (
                                        <tr key={index} className="border-b hover:bg-muted/30">
                                            <td className="p-3 font-medium">{item.term}</td>
                                            <td className="p-3">{item.originalTranslation}</td>
                                            <td className="p-3">{item.overrideTranslation}</td>
                                            <td className="p-3">{item.frequency}</td>
                                            <td className="p-3">{item.qualityDelta.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}
        </TabsContent>

        {/* Multi-Engine Tab (This tab is now using data from dashboardData.multiEngine) */}
        <TabsContent value="multi-engine" className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Multi-Engine Selection Trends</CardTitle>
                    <CardDescription>Trends in how different MT engines and combinations are selected.</CardDescription>
                </CardHeader>
                <CardContent>
                    {dashboardData.multiEngine.selectionTrends.length > 0 ? (
                        <ChartContainer config={preferenceChartConfig} className="h-[400px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={dashboardData.multiEngine.selectionTrends}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="selectionMethod" angle={-45} textAnchor="end" height={100} />
                                    <YAxis />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <Legend />
                                    <Bar dataKey="count" fill="var(--color-count)" name="Selection Count" />
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartContainer>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No multi-engine selection trend data available.
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Pivot Translation Quality</CardTitle>
                    <CardDescription>Quality analysis for pivot translations (e.g., JP-EN-FR).</CardDescription>
                </CardHeader>
                <CardContent>
                    {dashboardData.multiEngine.pivotQuality.length > 0 ? (
                        <div className="rounded-md border">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b bg-muted/50">
                                        <th className="p-3 text-left">Model Combination</th>
                                        <th className="p-3 text-left">Direct Quality</th>
                                        <th className="p-3 text-left">Pivot Quality</th>
                                        <th className="p-3 text-left">Intermediate Quality</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {dashboardData.multiEngine.pivotQuality.map((item, index) => (
                                        <tr key={index} className="border-b hover:bg-muted/30">
                                            <td className="p-3 font-medium">{item.modelCombination}</td>
                                            <td className="p-3">{item.directQuality.toFixed(2)}</td>
                                            <td className="p-3">{item.pivotQuality.toFixed(2)}</td>
                                            <td className="p-3">{item.intermediateQuality.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No pivot quality data available.
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Inter-Rater Agreement</CardTitle>
                    <CardDescription>Agreement scores between different annotators.</CardDescription>
                </CardHeader>
                <CardContent>
                    {dashboardData.multiEngine.interRaterAgreement.length > 0 ? (
                        <div className="rounded-md border">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b bg-muted/50">
                                        <th className="p-3 text-left">Annotator Pair</th>
                                        <th className="p-3 text-left">Agreement</th>
                                        <th className="p-3 text-left">Category</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {dashboardData.multiEngine.interRaterAgreement.map((item, index) => (
                                        <tr key={index} className="border-b hover:bg-muted/30">
                                            <td className="p-3 font-medium">{item.annotatorPair}</td>
                                            <td className="p-3">{item.agreement.toFixed(2)}</td>
                                            <td className="p-3">{item.category}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No inter-rater agreement data available.
                        </div>
                    )}
                </CardContent>
            </Card>
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