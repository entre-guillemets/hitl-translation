// src/pages/QualityDashboard.tsx

"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertTriangle, Check, ChevronDown, Download, RefreshCw, X } from 'lucide-react';
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
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { API_BASE_URL } from '@/config/api';

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
  avgCometKiwi: number;
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
  cometKiwiScore: number;
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

interface EvaluationModeEntry {
  mode: string;
  count: number;
  avgScore: number;
  confidence: number;
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

interface IAABreakdown {
  n: number;
  cohen_kappa: number | null;
  krippendorff_alpha: number | null;
  interpretation_kappa: string;
  interpretation_alpha: string;
}

interface IAAByPair extends IAABreakdown {
  language_pair: string;
}

interface IAAByAnnotator extends IAABreakdown {
  annotator: string;
}

interface IAAData extends IAABreakdown {
  by_language_pair: IAAByPair[];
  by_annotator: IAAByAnnotator[];
  data_source: string;
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

interface LLMJudgeSummaryEntry {
  languagePair: string;
  n: number;
  avgAdequacy: number | null;
  avgFluency: number | null;
  avgConfidence: number | null;
  avgCometDisagreement: number | null;
  highDisagreementCount: number;
}

interface LLMJudgeSummary {
  languagePairs: LLMJudgeSummaryEntry[];
  totalJudgments: number;
}

interface EvalSnapshot {
  id: string;
  requestId: string | null;
  languagePair: string;
  engineName: string | null;
  runDate: string;
  avgBleu: number | null;
  avgComet: number | null;
  avgChrf: number | null;
  avgTer: number | null;
  segmentCount: number;
  notes: string | null;
}

interface RegressionReportEntry {
  languagePair: string;
  engineName: string | null;
  status: 'ok' | 'regression' | 'insufficient_data';
  message?: string;
  latest: { id: string; runDate: string; notes: string | null; segmentCount: number; avgBleu: number | null; avgComet: number | null; avgChrf: number | null; avgTer: number | null };
  previous: { id: string; runDate: string; notes: string | null; segmentCount: number; avgBleu: number | null; avgComet: number | null; avgChrf: number | null; avgTer: number | null } | null;
  deltas: { bleu: number | null; comet: number | null; chrf: number | null; ter: number | null } | null;
  regressions: { metric: string; delta: number; threshold: number }[];
}

interface MetricReliabilityInfo {
  reliability: 'high' | 'medium' | 'low';
  reason: string;
}

interface MetricReliabilityData {
  language_pair: string;
  source_language: { code: string; name: string; script: string; notes: string | null };
  target_language: { code: string; name: string; script: string; tokenization_strategy: string; notes: string | null };
  primary_script: string;
  primary_notes: string | null;
  sample_size: number;
  bleu_std: number | null;
  min_reliable_sample_size: number;
  reliability_warning: boolean;
  metric_reliability_warning: boolean;
  statistical_confidence_warning: boolean;
  warning_reasons: string[];
  recommended_primary_metric: string;
  metrics: Record<string, MetricReliabilityInfo>;
  data_source: string;
}

interface EvalCoverageSignal {
  count: number;
  pct: number;
}

interface EvalCoverageRow {
  language_pair: string;
  total: number;
  signals: {
    qe_score: EvalCoverageSignal;
    post_edit: EvalCoverageSignal;
    bleu: EvalCoverageSignal;
    comet: EvalCoverageSignal;
    ter: EvalCoverageSignal;
    chrf: EvalCoverageSignal;
    llm_judge: EvalCoverageSignal;
  };
}

interface EvalCorrEntry {
  metric1: string;
  metric2: string;
  r: number;
  n: number;
}

interface EvalCorrByPair {
  language_pair: string;
  n: number;
  correlations: EvalCorrEntry[];
}

interface EvalCalibration {
  language_pair: string;
  n: number;
  ter_adequacy_r: number;
  interpretation: string;
}

interface EvalQualityData {
  coverage: EvalCoverageRow[];
  correlations_by_pair: EvalCorrByPair[];
  judge_calibration: EvalCalibration[];
}

interface SegmentConfPair {
  language_pair: string;
  count: number;
  scoreable: number;
  mean_confidence: number | null;
  min_confidence: number | null;
  max_confidence: number | null;
}

interface SegmentConfLow {
  segment_id: string;
  language_pair: string;
  confidence: number | null;
  n_signals: number;
  mean_quality: number | null;
}

interface SegmentConfidenceData {
  by_pair: SegmentConfPair[];
  lowest_confidence: SegmentConfLow[];
  total: number;
  scoreable: number;
}

interface BenchmarkEngineResult {
  engine: string;
  bleu: number | null;
  chrf: number | null;
  ter: number | null;
  comet: number | null;
  n_segments: number;
  snapshot_id: string;
  error: string | null;
}

interface BenchmarkRunResult {
  success: boolean;
  language_pair: string;
  request_id: string;
  n_sentences: number;
  engines_run: number;
  comet_available: boolean;
  notes: string | null;
  comparison: BenchmarkEngineResult[];
}

interface LLMDisagreementEntry {
  translationStringId: string;
  engineName: string | null;
  languagePair: string | null;
  sourceText: string | null;
  hypothesis: string | null;
  humanReference: string | null;
  adequacyScore: number;
  fluencyScore: number;
  confidenceScore: number;
  cometDisagreement: number | null;
  rationale: string | null;
  judgeModel: string;
  createdAt: string;
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
  cometKiwiScore: {
    label: "COMETKiwi Score",
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

const regressionChartConfig = {
  bleu: { label: "BLEU (×100)", color: "hsl(var(--chart-1))" },
  comet: { label: "COMET", color: "hsl(var(--chart-2))" },
  chrf: { label: "ChrF", color: "hsl(var(--chart-3))" },
  ter: { label: "TER (lower=better)", color: "hsl(var(--chart-4))" },
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

// Global MultiSelect component
const MultiSelect: React.FC<{
  options: { label: string; value: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
}> = ({ options, selected, onChange, placeholder }) => {
  const [open, setOpen] = React.useState(false);

  const toggle = (value: string) => {
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]);
  };

  const label = selected.length === 0
    ? placeholder
    : selected.length === 1
      ? (options.find(o => o.value === selected[0])?.label ?? selected[0])
      : `${selected.length} selected`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="min-w-[160px] justify-between font-normal">
          <span className="truncate">{label}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[220px] p-2" align="start">
        <div className="space-y-0.5 max-h-60 overflow-y-auto">
          {options.map(option => (
            <div
              key={option.value}
              className="flex items-center gap-2 px-2 py-1.5 rounded text-sm cursor-pointer hover:bg-muted"
              onClick={() => toggle(option.value)}
            >
              <Checkbox
                checked={selected.includes(option.value)}
                onCheckedChange={() => toggle(option.value)}
                onClick={e => e.stopPropagation()}
              />
              <span>{option.label}</span>
              {selected.includes(option.value) && <Check className="ml-auto h-3 w-3 text-primary" />}
            </div>
          ))}
          {options.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-2">No options available</p>
          )}
        </div>
        {selected.length > 0 && (
          <div className="border-t mt-2 pt-2">
            <Button variant="ghost" size="sm" className="w-full h-7 text-xs" onClick={() => onChange([])}>
              <X className="h-3 w-3 mr-1" /> Clear all
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
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
// Multi-Metric Chart Component
const MultiMetricChart: React.FC<{ data: ModelLeaderboardEntry[] }> = ({ data }) => {
  const chartData = data.map(item => ({
    name: item.name || item.model,
    avgBleu: item.avgBleu != null ? parseFloat(item.avgBleu.toFixed(1)) : null,
    avgComet: item.avgComet != null ? parseFloat(item.avgComet.toFixed(1)) : null,
    avgTer: item.avgTer != null ? parseFloat(item.avgTer.toFixed(1)) : null,
    avgChrf: item.avgChrf != null ? parseFloat(item.avgChrf.toFixed(1)) : null,
  }));

  return (
    <ChartContainer config={multiMetricChartConfig} className="h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 20, right: 30, left: 40, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={100}
            interval={0}
          />
          <YAxis
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => v.toFixed(0)}
            width={45}
          />
          <ChartTooltip
            content={<ChartTooltipContent />}
            formatter={(v: number) => v != null ? v.toFixed(1) : '—'}
          />
          <Bar dataKey="avgBleu" fill="var(--color-avgBleu)" name="BLEU Score (%)" />
          <Bar dataKey="avgComet" fill="var(--color-avgComet)" name="COMET (×100)" />
          <Bar dataKey="avgTer" fill="var(--color-avgTer)" name="TER Score (%)" />
          <Bar dataKey="avgChrf" fill="var(--color-avgChrf)" name="ChrF Score (%)" />
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

  // Controlled tab state (prevents tab resets on data refetch)
  const [activeTab, setActiveTab] = useState<string>('quality');
  const [evalMode, setEvalMode] = useState<'translation' | 'multi-agent'>('translation');

  // Global multiselect filters — pending = what's in the dropdowns, selected = what's applied
  const [selectedLanguagePairs, setSelectedLanguagePairs] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [pendingLanguagePairs, setPendingLanguagePairs] = useState<string[]>([]);
  const [pendingModels, setPendingModels] = useState<string[]>([]);
  const hasPendingChanges = pendingLanguagePairs.join() !== selectedLanguagePairs.join() || pendingModels.join() !== selectedModels.join();

  // State for chart controls
  const [chartGroupBy, setChartGroupBy] = useState<'model' | 'language_pair'>('model');
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});

  // Regression / snapshot data
  const [snapshots, setSnapshots] = useState<EvalSnapshot[]>([]);
  const [regressionReport, setRegressionReport] = useState<RegressionReportEntry[]>([]);

  // Metric reliability — keyed by "SRC-TGT" language pair
  const [reliabilityData, setReliabilityData] = useState<Record<string, MetricReliabilityData>>({});

  // Configured engines — seeds the model filter independently of whether metrics exist yet
  const [configuredEngines, setConfiguredEngines] = useState<{ id: string; name: string }[]>([]);

  // Pagination states for Translator Impact Analysis
  const [currentPageTranslator, setCurrentPageTranslator] = useState(1);
  const [itemsPerPageTranslator, setItemsPerPageTranslator] = useState(25);
  const itemsPerPageOptionsTranslator = [25, 50, 100, 0]; // 0 for All

  const [llmJudgeSummary, setLlmJudgeSummary] = useState<LLMJudgeSummary | null>(null);
  const [llmDisagreements, setLlmDisagreements] = useState<LLMDisagreementEntry[]>([]);
  const [llmJudgeRunning, setLlmJudgeRunning] = useState(false);
  const [iaaData, setIaaData] = useState<IAAData | null>(null);
  const [evalQualityData, setEvalQualityData] = useState<EvalQualityData | null>(null);
  const [segmentConfidenceData, setSegmentConfidenceData] = useState<SegmentConfidenceData | null>(null);
  const [currentPageDisagreements, setCurrentPageDisagreements] = useState(1);
  const DISAGREEMENTS_PAGE_SIZE = 25;

  // Filter states for Detailed Engine Preferences
  const [preferencesEngineFilter, setPreferencesEngineFilter] = useState<string>('all');
  const [preferencesLanguagePairFilter, setPreferencesLanguagePairFilter] = useState<string>('all');
  // Pagination states for Detailed Engine Preferences
  const [currentPagePreferences, setCurrentPagePreferences] = useState(1);
  const [itemsPerPagePreferences, setItemsPerPagePreferences] = useState(25);
  const itemsPerPageOptionsPreferences = [25, 50, 100, 0];

  // Benchmark runner state
  const [benchmarkPair, setBenchmarkPair] = useState<string>('en-fr');
  const [benchmarkNotes, setBenchmarkNotes] = useState<string>('baseline');
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkRunResult | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);


  // Normalize JA↔JP aliases to a single canonical pair string (DB uses JP for Japanese)
  const normalizePair = (lp: string) => lp.toUpperCase().replace(/^JA-/, 'JP-').replace(/-JA$/, '-JP');

  // ── Available filter options (derived from loaded data) ──────────────────
  const availableLanguagePairs = useMemo(() => {
    const pairs = new Set<string>();
    dashboardData?.modelPerformance.leaderboard.forEach(e => e.languagePairs?.forEach(p => pairs.add(normalizePair(p))));
    postEditData?.languagePairMetrics.forEach(e => pairs.add(normalizePair(e.languagePair)));
    translatorImpactData?.comparisons.forEach(e => pairs.add(normalizePair(e.languagePair)));
    snapshots.forEach(s => pairs.add(normalizePair(s.languagePair)));
    llmDisagreements.forEach(r => { if (r.languagePair) pairs.add(normalizePair(r.languagePair)); });
    return Array.from(pairs).filter(Boolean).sort().map(p => ({ label: p, value: p }));
  }, [dashboardData, postEditData, translatorImpactData, snapshots, llmDisagreements]);

  const availableModels = useMemo(() => {
    const models = new Map<string, string>();
    configuredEngines.forEach(e => models.set(e.id, e.name));
    // Track display names already covered to avoid duplicates when leaderboard/snapshot
    // entries use display names (e.g. "Gemini Transcreation") instead of IDs.
    const knownLabels = new Set(models.values());
    dashboardData?.modelPerformance.leaderboard.forEach(e => {
      const name = e.name || e.model;
      if (name && !models.has(name) && !knownLabels.has(name)) {
        models.set(name, name);
        knownLabels.add(name);
      }
    });
    snapshots.forEach(s => {
      if (s.engineName && !models.has(s.engineName) && !knownLabels.has(s.engineName)) {
        models.set(s.engineName, s.engineName);
        knownLabels.add(s.engineName);
      }
    });
    return Array.from(models.entries())
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([id, label]) => ({ label, value: id }));
  }, [dashboardData, snapshots, configuredEngines]);

  // ── Global client-side filtered views ────────────────────────────────────
  const matchLP = (lp: string | undefined) =>
    selectedLanguagePairs.length === 0 || (lp != null && selectedLanguagePairs.includes(normalizePair(lp)));
  const matchModel = (name: string | undefined) =>
    selectedModels.length === 0 || (name != null && selectedModels.includes(name));

  const filteredLeaderboard = useMemo(() =>
    (dashboardData?.modelPerformance.leaderboard ?? []).filter(e => {
      const modelName = e.name || e.model;
      if (!matchModel(modelName)) return false;
      if (selectedLanguagePairs.length > 0 && e.languagePairs) {
        return e.languagePairs.some(p => selectedLanguagePairs.includes(p));
      }
      return true;
    }),
  [dashboardData, selectedLanguagePairs, selectedModels]);

  const filteredPostEditMetrics = useMemo(() =>
    (postEditData?.languagePairMetrics ?? []).filter(e => matchLP(e.languagePair)),
  [postEditData, selectedLanguagePairs]);

  const filteredTranslatorComparisons = useMemo(() =>
    (translatorImpactData?.comparisons ?? []).filter(e => matchLP(e.languagePair)),
  [translatorImpactData, selectedLanguagePairs]);

  // Snapshots filtered by both language pair and engine (model)
  const filteredSnapshots = useMemo(() =>
    snapshots.filter(s =>
      matchLP(s.languagePair) &&
      (selectedModels.length === 0 || (s.engineName != null && selectedModels.includes(s.engineName)))
    ),
  [snapshots, selectedLanguagePairs, selectedModels]);

  // Latest snapshot per (languagePair, engineName) for the regression chart
  const regressionChartData = useMemo(() => {
    const byKey: Record<string, EvalSnapshot> = {};
    for (const s of filteredSnapshots) {
      const key = `${s.languagePair}|${s.engineName ?? 'agg'}`;
      if (!byKey[key] || s.runDate > byKey[key].runDate) byKey[key] = s;
    }
    // avgBleu stored 0–1, multiply ×100. avgComet stored as raw COMET-DA (0–1.5 range),
    // multiply ×100 to put it on the same scale as BLEU/ChrF/TER.
    // avgChrf and avgTer are already 0–100.
    return Object.values(byKey).map(s => ({
      name: s.engineName ? `${s.languagePair} (${s.engineName})` : s.languagePair,
      bleu:  s.avgBleu  != null ? parseFloat(s.avgBleu.toFixed(1))          : null,
      comet: s.avgComet != null ? parseFloat((s.avgComet * 100).toFixed(1)) : null,
      chrf:  s.avgChrf  != null ? parseFloat(s.avgChrf.toFixed(1))          : null,
      ter:   s.avgTer   != null ? parseFloat(s.avgTer.toFixed(1))           : null,
      notes: s.notes,
      runDate: s.runDate,
    }));
  }, [filteredSnapshots]);

  const filteredRegressionReport = useMemo(() =>
    regressionReport.filter(r =>
      matchLP(r.languagePair) &&
      (selectedModels.length === 0 || r.engineName == null || selectedModels.includes(r.engineName))
    ),
  [regressionReport, selectedLanguagePairs, selectedModels]);

  const filteredLlmDisagreements = useMemo(() =>
    llmDisagreements.filter(r => matchLP(r.languagePair ?? undefined)),
  [llmDisagreements, selectedLanguagePairs]);

  const paginatedLlmDisagreements = useMemo(() => {
    const start = (currentPageDisagreements - 1) * DISAGREEMENTS_PAGE_SIZE;
    return filteredLlmDisagreements.slice(start, start + DISAGREEMENTS_PAGE_SIZE);
  }, [filteredLlmDisagreements, currentPageDisagreements]);

  const totalPagesDisagreements = Math.max(1, Math.ceil(filteredLlmDisagreements.length / DISAGREEMENTS_PAGE_SIZE));

  // ── Translator Impact pagination (uses filtered comparisons) ─────────────
  const paginatedTranslatorComparisons = useMemo(() => {
    if (filteredTranslatorComparisons.length === 0) return [];
    const startIndex = (currentPageTranslator - 1) * itemsPerPageTranslator;
    const endIndex = itemsPerPageTranslator === 0 ? filteredTranslatorComparisons.length : startIndex + itemsPerPageTranslator;
    return filteredTranslatorComparisons.slice(startIndex, endIndex);
  }, [filteredTranslatorComparisons, currentPageTranslator, itemsPerPageTranslator]);

  const totalTranslatorComparisonsCount = filteredTranslatorComparisons.length;
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

  // Single language pair for API calls — pass first selected item when exactly one is chosen
  const apiLanguagePair = selectedLanguagePairs.length === 1 ? selectedLanguagePairs[0] : undefined;

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        group_by: chartGroupBy,
        ...(apiLanguagePair && { language_pair: apiLanguagePair }),
        ...(dateRange?.from && { date_from: dateRange.from }),
        ...(dateRange?.to && { date_to: dateRange.to }),
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/analytics?${params}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      setDashboardData(await response.json());
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
        ...(apiLanguagePair && { language_pair: apiLanguagePair }),
        ...(dateRange?.from && { date_from: dateRange.from }),
        ...(dateRange?.to && { date_to: dateRange.to }),
      });
      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/post-edit-metrics?${params}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      setPostEditData(await response.json());
    } catch (err) {
      console.error('Failed to fetch post-edit data:', err);
    }
  };

  const fetchTranslatorImpactData = async () => {
    try {
      const params = new URLSearchParams({
        ...(apiLanguagePair && { language_pair: apiLanguagePair }),
      });
      const response = await fetch(`${API_BASE_URL}/api/analytics/dashboard/translator-impact?${params}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      setTranslatorImpactData(await response.json());
    } catch (err) {
      console.error('Failed to fetch translator impact data:', err);
    }
  };

  const fetchLlmJudgeData = async () => {
    try {
      const [summaryRes, disagreementsRes, iaaRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/llm-judge/summary`),
        fetch(`${API_BASE_URL}/api/llm-judge/disagreements?limit=50`),
        fetch(`${API_BASE_URL}/api/analytics/annotator-agreement`),
      ]);
      if (summaryRes.ok) setLlmJudgeSummary(await summaryRes.json());
      if (disagreementsRes.ok) {
        const data = await disagreementsRes.json();
        setLlmDisagreements(data.disagreements ?? []);
      }
      if (iaaRes.ok) setIaaData(await iaaRes.json());
    } catch (err) {
      console.error('Failed to fetch LLM judge data:', err);
    }
  };

  const fetchSnapshotData = async () => {
    try {
      const [snapshotsRes, reportRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/benchmarks/snapshots?limit=200`),
        fetch(`${API_BASE_URL}/api/benchmarks/regression-report`),
      ]);
      if (snapshotsRes.ok) {
        const data = await snapshotsRes.json();
        setSnapshots(data.snapshots ?? []);
      }
      if (reportRes.ok) {
        const data = await reportRes.json();
        setRegressionReport(data.report ?? []);
      }
    } catch (err) {
      console.error('Failed to fetch snapshot data:', err);
    }
  };

  const runLlmJudge = async () => {
    setLlmJudgeRunning(true);
    try {
      await fetch(`${API_BASE_URL}/api/llm-judge/evaluate-all-approved?limit=10`, { method: 'POST' });
      await fetchLlmJudgeData();
    } finally {
      setLlmJudgeRunning(false);
    }
  };

  // Fetch configured engines once on mount — populates model dropdown before any metrics exist
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/health/engines`)
      .then(r => r.ok ? r.json() : { engines: [] })
      .then(data => setConfiguredEngines(data.engines ?? []))
      .catch(() => {});
  }, []);

  // Fetch reliability data for all language pairs known to the dashboard
  const fetchReliabilityData = async (pairs: string[]) => {
    if (pairs.length === 0) return;
    const results = await Promise.allSettled(
      pairs.map(lp =>
        fetch(`${API_BASE_URL}/api/analytics/metric-reliability/${encodeURIComponent(lp)}`)
          .then(r => r.ok ? r.json() : null)
      )
    );
    const map: Record<string, MetricReliabilityData> = {};
    results.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value) {
        map[pairs[i].toUpperCase()] = r.value;
      }
    });
    setReliabilityData(prev => ({ ...prev, ...map }));
  };

  const fetchEvalQualityData = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/analytics/eval-quality`);
      if (res.ok) setEvalQualityData(await res.json());
    } catch (err) {
      console.error('Failed to fetch eval quality data:', err);
    }
  };

  const fetchSegmentConfidenceData = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/analytics/segment-confidence`);
      if (res.ok) setSegmentConfidenceData(await res.json());
    } catch (err) {
      console.error('Failed to fetch segment confidence data:', err);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchPostEditData();
    fetchTranslatorImpactData();
    fetchLlmJudgeData();
    fetchSnapshotData();
    fetchEvalQualityData();
    fetchSegmentConfidenceData();
  }, [chartGroupBy, selectedLanguagePairs, selectedModels, dateRange]);

  // Fetch reliability data for all known language pairs.
  // Includes coverage rows so SW and other pairs show reliability notes even before QA metrics exist.
  useEffect(() => {
    const seen = new Set<string>();
    const pairs: string[] = [];
    const add = (p: string) => { const u = normalizePair(p); if (u && !seen.has(u)) { seen.add(u); pairs.push(u); } };
    dashboardData?.modelPerformance.leaderboard.forEach(e => e.languagePairs?.forEach(p => p && add(p)));
    postEditData?.languagePairMetrics.forEach(e => e.languagePair && add(e.languagePair));
    evalQualityData?.coverage.forEach(r => add(r.language_pair));
    fetchReliabilityData(pairs);
  }, [dashboardData, postEditData, evalQualityData]);

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

  const fmtBleu  = (v: number | null | undefined) => v != null ? v.toFixed(1) : '—';
  const fmtChrf  = (v: number | null | undefined) => v != null ? v.toFixed(1) : '—';
  const fmtTer   = (v: number | null | undefined) => v != null ? v.toFixed(1) : '—';
  const fmtComet = (v: number | null | undefined) => v != null ? v.toFixed(3) : '—';

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

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-10">
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="translator-impact">Translator Impact</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="annotations">Annotations</TabsTrigger>
          <TabsTrigger value="tm-glossary">TM & Glossary</TabsTrigger>
          <TabsTrigger value="llm-judge">LLM Judge</TabsTrigger>
          <TabsTrigger value="regression">Regression</TabsTrigger>
          <TabsTrigger value="eval-quality">Eval Quality</TabsTrigger>
          <TabsTrigger value="benchmark">Benchmark</TabsTrigger>
        </TabsList>

        {/* ── Evaluation mode toggle ─────────────────────────────────────── */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Eval mode:</span>
          <div className="flex rounded-md border overflow-hidden text-xs">
            <button
              type="button"
              onClick={() => setEvalMode("translation")}
              className={`px-3 py-1.5 transition-colors ${evalMode === "translation" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            >
              Translation Evals
            </button>
            <button
              type="button"
              onClick={() => setEvalMode("multi-agent")}
              className={`px-3 py-1.5 border-l transition-colors ${evalMode === "multi-agent" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            >
              Multi-Agent Evals
            </button>
          </div>
          {evalMode === "multi-agent" && (
            <span className="text-xs text-muted-foreground">
              Showing brand voice / cultural fitness scores. BLEU/TER are not shown — surface metrics penalise intentional creative adaptation.
            </span>
          )}
        </div>

        {/* ── Global filters bar ─────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3 px-3 py-2.5 rounded-lg border bg-muted/30">
          <span className="text-sm font-medium text-muted-foreground shrink-0">Filters:</span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Language pair</span>
            <MultiSelect
              options={availableLanguagePairs}
              selected={pendingLanguagePairs}
              onChange={setPendingLanguagePairs}
              placeholder="All pairs"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Model</span>
            <MultiSelect
              options={availableModels}
              selected={pendingModels}
              onChange={setPendingModels}
              placeholder="All models"
            />
          </div>
          <Button
            size="sm"
            className="h-8 text-xs"
            disabled={!hasPendingChanges}
            onClick={() => { setSelectedLanguagePairs(pendingLanguagePairs); setSelectedModels(pendingModels); }}
          >
            Apply
          </Button>
          {(selectedLanguagePairs.length > 0 || selectedModels.length > 0) && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => { setPendingLanguagePairs([]); setPendingModels([]); setSelectedLanguagePairs([]); setSelectedModels([]); }}
            >
              <X className="h-3 w-3 mr-1" />
              Clear
            </Button>
          )}
          {(selectedLanguagePairs.length > 0 || selectedModels.length > 0) && (
            <Badge variant="secondary" className="ml-auto text-xs">
              Filtering active
            </Badge>
          )}
        </div>

        {/* NEW: Quality Tab */}
        <TabsContent value="quality" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {/* Post-Edit Metrics */}
              {postEditData && (() => {
                const postEditChartData = filteredPostEditMetrics.map(e => ({
                  ...e,
                  avgCometScaled: e.avgComet != null ? parseFloat((e.avgComet * 100).toFixed(1)) : null,
                }));
                return (
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
                          <BarChart data={postEditChartData}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="languagePair" />
                            <YAxis domain={['auto', 'auto']} tickFormatter={(v: number) => Math.round(v).toString()} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Legend />
                            <Bar dataKey="avgBleu" fill="var(--color-avgBleu)" name="BLEU (0–100)" />
                            <Bar dataKey="avgCometScaled" fill="var(--color-avgComet)" name="COMET (×100)" />
                            <Bar dataKey="avgTer" fill="var(--color-avgTer)" name="TER (0–100, lower=better)" />
                            <Bar dataKey="avgChrf" fill="var(--color-avgChrf)" name="ChrF (0–100)" />
                          </BarChart>
                        </ResponsiveContainer>
                      </ChartContainer>
                    </CardContent>
                  </Card>
                );
              })()}
            </div>
            <div className="lg:col-span-1">
              {/* Correlation Matrix */}
              {postEditData && postEditData.correlationMatrix.length > 0 && (
                <MetricCorrelationMatrix data={postEditData.correlationMatrix} />
              )}
            </div>
          </div>

          {/* Metric Reliability Summary — consolidated card, one row per warned language pair */}
          {(() => {
            const seen = new Set<string>();
            const warnedPairs = filteredPostEditMetrics
              .map(e => reliabilityData[normalizePair(e.languagePair ?? '')])
              .filter((r): r is MetricReliabilityData => {
                if (!r?.reliability_warning) return false;
                const key = normalizePair(r.language_pair);
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
              });
            if (warnedPairs.length === 0) return null;
            return (
              <Card className="border-yellow-500/30">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base text-yellow-600 dark:text-yellow-400">
                    <AlertTriangle className="h-4 w-4" />
                    Metric Reliability Notes
                  </CardTitle>
                  <CardDescription>
                    Automatic metrics have known limitations for some language pairs. COMET and ChrF are recommended over BLEU/TER where flagged.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-md border text-sm">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/50 text-xs">
                          <th className="p-2 text-left">Pair</th>
                          <th className="p-2 text-left">Script</th>
                          <th className="p-2 text-left">n</th>
                          <th className="p-2 text-left">BLEU</th>
                          <th className="p-2 text-left">TER</th>
                          <th className="p-2 text-left">ChrF</th>
                          <th className="p-2 text-left">COMET</th>
                          <th className="p-2 text-left">Primary Signal</th>
                          <th className="p-2 text-left">Warning Type</th>
                          <th className="p-2 text-left">Notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {warnedPairs.map(r => {
                          const reliabilityBadge = (level: string) => (
                            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${
                              level === 'high' ? 'bg-green-500/15 text-green-700 dark:text-green-400' :
                              level === 'medium' ? 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400' :
                              'bg-red-500/15 text-red-700 dark:text-red-400'
                            }`}>
                              {level === 'high' ? '✓' : level === 'medium' ? '~' : '⚠'} {level}
                            </span>
                          );
                          const sampleWarning = r.statistical_confidence_warning;
                          const metricWarning = r.metric_reliability_warning;
                          return (
                            <tr key={r.language_pair} className="border-b hover:bg-muted/20">
                              <td className="p-2 font-medium">{r.language_pair}</td>
                              <td className="p-2 text-muted-foreground">{r.primary_script}</td>
                              <td className="p-2">
                                <span className={sampleWarning ? 'text-yellow-600 dark:text-yellow-400 font-medium' : ''}>
                                  {r.sample_size}{sampleWarning ? ` / ${r.min_reliable_sample_size}` : ''}
                                </span>
                              </td>
                              <td className="p-2">{r.metrics.bleu ? reliabilityBadge(r.metrics.bleu.reliability) : '—'}</td>
                              <td className="p-2">{r.metrics.ter ? reliabilityBadge(r.metrics.ter.reliability) : '—'}</td>
                              <td className="p-2">{r.metrics.chrf ? reliabilityBadge(r.metrics.chrf.reliability) : '—'}</td>
                              <td className="p-2">{r.metrics.comet ? reliabilityBadge(r.metrics.comet.reliability) : '—'}</td>
                              <td className="p-2 text-xs font-medium text-blue-700 dark:text-blue-400">{r.recommended_primary_metric}</td>
                              <td className="p-2">
                                <div className="flex flex-col gap-1">
                                  {metricWarning && (
                                    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-red-500/15 text-red-700 dark:text-red-400">
                                      Metric
                                    </span>
                                  )}
                                  {sampleWarning && (
                                    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-yellow-500/15 text-yellow-700 dark:text-yellow-400">
                                      Sample
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="p-2 text-xs text-muted-foreground max-w-xs">{r.primary_notes ?? '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            );
          })()}

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
              <div className="flex items-center gap-3 mb-4">
                <span className="text-sm font-medium">Group by:</span>
                <Select value={chartGroupBy} onValueChange={(v) => setChartGroupBy(v as 'model' | 'language_pair')}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="model">Model</SelectItem>
                    <SelectItem value="language_pair">Language Pair</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {filteredLeaderboard.length > 0 ? (
                <MultiMetricChart data={filteredLeaderboard} />
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No performance data available for the selected criteria. Ensure there are human post-edits.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model Performance Leaderboard Table */}
          {filteredLeaderboard.length > 0 && (
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
                        <th className="p-3 text-left">BLEU (0–100)</th>
                        <th className="p-3 text-left">COMET (0–1)</th>
                        <th className="p-3 text-left">TER (0–100, lower=better)</th>
                        <th className="p-3 text-left">ChrF (0–100)</th>
                        <th className="p-3 text-left">Total Translations</th>
                        <th className="p-3 text-left">Reliability</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLeaderboard.map((item, index) => {
                        const warnedPairs = (item.languagePairs ?? [])
                          .map(lp => reliabilityData[lp?.toUpperCase()])
                          .filter(r => r?.reliability_warning);
                        return (
                        <tr key={index} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{item.name || item.model}</td>
                          <td className="p-3">{item.engineType}</td>
                          <td className="p-3">{fmtBleu(item.avgBleu)}</td>
                          <td className="p-3">{fmtComet(item.avgComet)}</td>
                          <td className="p-3">{fmtTer(item.avgTer)}</td>
                          <td className="p-3">{fmtChrf(item.avgChrf)}</td>
                          <td className="p-3">{item.totalTranslations}</td>
                          <td className="p-3">
                            {warnedPairs.length > 0 ? (
                              <span
                                className="inline-flex items-center gap-1 text-yellow-600 dark:text-yellow-400 text-xs"
                                title={warnedPairs.map(r => `${r.language_pair}: ${r.warning_reasons.join('; ')}`).join('\n')}
                              >
                                <AlertTriangle className="h-3.5 w-3.5" />
                                {warnedPairs.map(r => r.language_pair).join(', ')}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                                <Check className="h-3.5 w-3.5" /> OK
                              </span>
                            )}
                          </td>
                        </tr>
                        );
                      })}
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
                      <YAxis domain={['auto', 'auto']} tickFormatter={(v: number) => v.toFixed(0)} width={45} />
                      <ChartTooltip content={<ChartTooltipContent />} formatter={(v: number) => v.toFixed(1)} />
                      <Area type="monotone" dataKey="bleuScore" stroke="var(--color-bleuScore)" fill="var(--color-bleuScore)" fillOpacity={0.3} />
                      <Area type="monotone" dataKey="cometScore" stroke="var(--color-cometScore)" fill="var(--color-cometScore)" fillOpacity={0.3} />
                      <Area type="monotone" dataKey="cometKiwiScore" stroke="var(--color-cometKiwiScore)" fill="var(--color-cometKiwiScore)" fillOpacity={0.3} />
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
          
          {/* Error Severity Distribution */}
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
                    <CardTitle>Human–LLM Judge Agreement (IAA)</CardTitle>
                    <CardDescription>
                      Cohen's κ and Krippendorff's α between human post-editing effort (TER) and LLM judge adequacy.
                      See the LLM Judge tab for full per-language-pair breakdown.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {iaaData && iaaData.n > 0 ? (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="rounded-lg border p-4">
                                <p className="text-sm text-muted-foreground mb-1">Cohen's κ</p>
                                <p className="text-2xl font-bold">
                                  {iaaData.cohen_kappa != null ? iaaData.cohen_kappa.toFixed(3) : '—'}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">{iaaData.interpretation_kappa}</p>
                            </div>
                            <div className="rounded-lg border p-4">
                                <p className="text-sm text-muted-foreground mb-1">Krippendorff's α</p>
                                <p className="text-2xl font-bold">
                                  {iaaData.krippendorff_alpha != null ? iaaData.krippendorff_alpha.toFixed(3) : '—'}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">{iaaData.interpretation_alpha}</p>
                            </div>
                            <p className="col-span-2 text-xs text-muted-foreground">n = {iaaData.n} paired segments</p>
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No paired data yet. IAA requires segments with both TER scores and LLM judge evaluations.
                        </div>
                    )}
                </CardContent>
            </Card>
        </TabsContent>

        {/* LLM Judge Tab */}
        <TabsContent value="llm-judge" className="space-y-6">
          {/* Header with run button */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">LLM-as-Judge Evaluation</h3>
              <p className="text-sm text-muted-foreground">
                Gemini scores MT outputs on adequacy and fluency. High disagreement with COMET identifies segments where automatic metrics give misleading confidence.
              </p>
            </div>
            <Button onClick={runLlmJudge} disabled={llmJudgeRunning} variant="outline">
              {llmJudgeRunning ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              {llmJudgeRunning ? 'Running…' : 'Run on All Approved'}
            </Button>
          </div>

          {/* Summary stats */}
          {llmJudgeSummary && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Total Judgments</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{llmJudgeSummary.totalJudgments}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">High Disagreement Segments</CardTitle>
                  <CardDescription>COMET vs adequacy delta &gt; 0.25</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold text-amber-600">
                    {llmJudgeSummary.languagePairs.reduce((sum, p) => sum + p.highDisagreementCount, 0)}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Per-language-pair summary table */}
          {llmJudgeSummary && llmJudgeSummary.languagePairs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Summary by Language Pair</CardTitle>
                <CardDescription>Average scores and disagreement signal per language pair</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Language Pair</th>
                        <th className="p-3 text-left">N</th>
                        <th className="p-3 text-left">Avg Adequacy</th>
                        <th className="p-3 text-left">Avg Fluency</th>
                        <th className="p-3 text-left">Avg Confidence</th>
                        <th className="p-3 text-left">Avg COMET Disagreement</th>
                        <th className="p-3 text-left">High Disagreement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {llmJudgeSummary.languagePairs.map((row, i) => (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{row.languagePair}</td>
                          <td className="p-3">{row.n}</td>
                          <td className="p-3">{row.avgAdequacy?.toFixed(2) ?? '—'} / 4</td>
                          <td className="p-3">{row.avgFluency?.toFixed(2) ?? '—'} / 4</td>
                          <td className="p-3">{row.avgConfidence?.toFixed(2) ?? '—'}</td>
                          <td className="p-3">
                            {row.avgCometDisagreement != null ? (
                              <Badge variant={row.avgCometDisagreement > 0.25 ? 'destructive' : 'default'}>
                                {row.avgCometDisagreement.toFixed(3)}
                              </Badge>
                            ) : '—'}
                          </td>
                          <td className="p-3">{row.highDisagreementCount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Disagreement table */}
          <Card>
            <CardHeader>
              <CardTitle>Top Disagreement Segments</CardTitle>
              <CardDescription>
                Segments where COMET and LLM judge diverge most — candidates for human review
              </CardDescription>
            </CardHeader>
            <CardContent>
              {filteredLlmDisagreements.length > 0 ? (
                <>
                  <div className="rounded-md border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-3 text-left">Pair</th>
                          <th className="p-3 text-left">Engine</th>
                          <th className="p-3 text-left w-1/4">Source</th>
                          <th className="p-3 text-left w-1/5">MT</th>
                          <th className="p-3 text-left">Adequacy</th>
                          <th className="p-3 text-left">Fluency</th>
                          <th className="p-3 text-left">Disagreement</th>
                          <th className="p-3 text-left w-1/3">Rationale</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedLlmDisagreements.map((row, i) => (
                          <tr key={i} className="border-b hover:bg-muted/30 align-top">
                            <td className="p-3">{row.languagePair ?? '—'}</td>
                            <td className="p-3">{row.engineName ?? 'single'}</td>
                            <td className="p-3">
                              <p className="break-words whitespace-pre-wrap">{row.sourceText ?? '—'}</p>
                            </td>
                            <td className="p-3">
                              <p className="break-words whitespace-pre-wrap text-muted-foreground">{row.hypothesis ?? '—'}</p>
                            </td>
                            <td className="p-3">{row.adequacyScore.toFixed(1)} / 4</td>
                            <td className="p-3">{row.fluencyScore.toFixed(1)} / 4</td>
                            <td className="p-3">
                              {row.cometDisagreement != null ? (
                                <Badge variant={row.cometDisagreement > 0.25 ? 'destructive' : 'secondary'}>
                                  {row.cometDisagreement.toFixed(3)}
                                </Badge>
                              ) : '—'}
                            </td>
                            <td className="p-3 text-muted-foreground">{row.rationale ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {totalPagesDisagreements > 1 && (
                    <div className="flex items-center justify-between mt-3 text-sm text-muted-foreground">
                      <span>
                        {((currentPageDisagreements - 1) * DISAGREEMENTS_PAGE_SIZE) + 1}–{Math.min(currentPageDisagreements * DISAGREEMENTS_PAGE_SIZE, filteredLlmDisagreements.length)} of {filteredLlmDisagreements.length}
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          className="px-2 py-1 rounded border disabled:opacity-40 hover:bg-muted"
                          onClick={() => setCurrentPageDisagreements(p => Math.max(1, p - 1))}
                          disabled={currentPageDisagreements === 1}
                        >
                          ‹ Prev
                        </button>
                        <span>Page {currentPageDisagreements} / {totalPagesDisagreements}</span>
                        <button
                          className="px-2 py-1 rounded border disabled:opacity-40 hover:bg-muted"
                          onClick={() => setCurrentPageDisagreements(p => Math.min(totalPagesDisagreements, p + 1))}
                          disabled={currentPageDisagreements === totalPagesDisagreements}
                        >
                          Next ›
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p>No LLM judgments yet. Click "Run on All Approved" to evaluate approved strings.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* IAA Card */}
          <Card>
            <CardHeader>
              <CardTitle>Human–LLM Judge Agreement (IAA)</CardTitle>
              <CardDescription>
                Cohen's κ (categorical) and Krippendorff's α (continuous) between
                human post-editing effort (TER-derived) and LLM adequacy scores.
                Single human annotator — "inter-annotator" = human vs. LLM judge.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {iaaData && iaaData.n > 0 ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground mb-1">Cohen's κ (global)</p>
                      <p className="text-2xl font-bold">
                        {iaaData.cohen_kappa != null ? iaaData.cohen_kappa.toFixed(3) : '—'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">{iaaData.interpretation_kappa}</p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground mb-1">Krippendorff's α (global)</p>
                      <p className="text-2xl font-bold">
                        {iaaData.krippendorff_alpha != null ? iaaData.krippendorff_alpha.toFixed(3) : '—'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">{iaaData.interpretation_alpha}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">n = {iaaData.n} paired segments</p>
                  {iaaData.by_language_pair.length > 0 && (
                    <>
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">By Language Pair</p>
                      <div className="rounded-md border">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b bg-muted/50">
                              <th className="p-3 text-left">Language Pair</th>
                              <th className="p-3 text-left">n</th>
                              <th className="p-3 text-left">Cohen's κ</th>
                              <th className="p-3 text-left">Krippendorff's α</th>
                              <th className="p-3 text-left">κ Interpretation</th>
                            </tr>
                          </thead>
                          <tbody>
                            {iaaData.by_language_pair.map((row, i) => (
                              <tr key={i} className="border-b hover:bg-muted/30">
                                <td className="p-3 font-medium">{row.language_pair}</td>
                                <td className="p-3">{row.n}</td>
                                <td className="p-3">{row.cohen_kappa != null ? row.cohen_kappa.toFixed(3) : '—'}</td>
                                <td className="p-3">{row.krippendorff_alpha != null ? row.krippendorff_alpha.toFixed(3) : '—'}</td>
                                <td className="p-3 text-muted-foreground">{row.interpretation_kappa}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                  {iaaData.by_annotator.length > 0 && (
                    <>
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">By Annotator</p>
                      <div className="rounded-md border">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b bg-muted/50">
                              <th className="p-3 text-left">Annotator</th>
                              <th className="p-3 text-left">n</th>
                              <th className="p-3 text-left">Cohen's κ</th>
                              <th className="p-3 text-left">Krippendorff's α</th>
                              <th className="p-3 text-left">κ Interpretation</th>
                            </tr>
                          </thead>
                          <tbody>
                            {iaaData.by_annotator.map((row, i) => (
                              <tr key={i} className="border-b hover:bg-muted/30">
                                <td className="p-3 font-medium">{row.annotator}</td>
                                <td className="p-3">{row.n}</td>
                                <td className="p-3">{row.cohen_kappa != null ? row.cohen_kappa.toFixed(3) : '—'}</td>
                                <td className="p-3">{row.krippendorff_alpha != null ? row.krippendorff_alpha.toFixed(3) : '—'}</td>
                                <td className="p-3 text-muted-foreground">{row.interpretation_kappa}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No paired segments yet. IAA requires segments with both TER scores and LLM judge evaluations.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        {/* ── Regression Tab ─────────────────────────────────────────────── */}
        <TabsContent value="regression" className="space-y-6">

          {/* Metric bars chart */}
          <Card>
            <CardHeader>
              <CardTitle>WMT Baseline Metrics by Language Pair</CardTitle>
              <CardDescription>
                Scores from the most recent snapshot per language pair / engine. BLEU is scaled ×100.
                TER is lower-is-better — high values indicate more post-editing effort.
                Use the global filters above to isolate a specific pair or model.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {regressionChartData.length > 0 ? (
                <ChartContainer config={regressionChartConfig} className="w-full h-[420px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={regressionChartData} margin={{ top: 90, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        orientation="top"
                        angle={-35}
                        textAnchor="start"
                        height={85}
                        interval={0}
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis domain={['auto', 'auto']} tickFormatter={(v: number) => v.toFixed(0)} width={40} />
                      <ChartTooltip
                        content={({ active, payload, label }) => {
                          if (!active || !payload?.length) return null;
                          const colors: Record<string, string> = {
                            bleu: 'var(--color-bleu)',
                            comet: 'var(--color-comet)',
                            chrf: 'var(--color-chrf)',
                            ter: 'var(--color-ter)',
                          };
                          const displayNames: Record<string, string> = { bleu: 'BLEU ×100', comet: 'COMET', chrf: 'ChrF', ter: 'TER' };
                          return (
                            <div className="rounded-lg border bg-background p-2.5 shadow-md text-xs min-w-[160px]">
                              <p className="font-semibold mb-1.5 text-foreground">{label}</p>
                              {payload.map(p => (
                                <div key={p.dataKey as string} className="flex items-center justify-between gap-4 py-0.5">
                                  <span className="flex items-center gap-1.5">
                                    <span className="inline-block w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: colors[p.dataKey as string] ?? p.color }} />
                                    <span className="text-muted-foreground">{displayNames[p.dataKey as string] ?? p.name}</span>
                                  </span>
                                  <span className="font-medium tabular-nums">{p.value != null ? (p.value as number).toFixed(1) : '—'}</span>
                                </div>
                              ))}
                            </div>
                          );
                        }}
                      />
                      <Legend verticalAlign="bottom" height={28} />
                      <Bar dataKey="bleu" name="BLEU ×100" fill="var(--color-bleu)" radius={[3,3,0,0]} />
                      <Bar dataKey="comet" name="COMET" fill="var(--color-comet)" radius={[3,3,0,0]} />
                      <Bar dataKey="chrf" name="ChrF" fill="var(--color-chrf)" radius={[3,3,0,0]} />
                      <Bar dataKey="ter" name="TER" fill="var(--color-ter)" radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p>No snapshot data available. Run <code className="text-xs bg-muted px-1 rounded">POST /api/benchmarks/snapshot</code> after running WMT evaluations.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Regression status table */}
          <Card>
            <CardHeader>
              <CardTitle>Regression Status</CardTitle>
              <CardDescription>
                Compares the two most recent snapshots per language pair / engine.
                A regression is flagged when BLEU drops &gt;2 pts, COMET drops &gt;0.02, ChrF drops &gt;2 pts, or TER rises &gt;2 pts.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {filteredRegressionReport.length > 0 ? (
                <div className="rounded-md border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Language Pair</th>
                        <th className="p-3 text-left">Engine</th>
                        <th className="p-3 text-left">Status</th>
                        <th className="p-3 text-left">ΔBLEU</th>
                        <th className="p-3 text-left">ΔCOMET</th>
                        <th className="p-3 text-left">ΔChrF</th>
                        <th className="p-3 text-left">ΔTER</th>
                        <th className="p-3 text-left">Latest run</th>
                        <th className="p-3 text-left">Segments</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRegressionReport.map((row, i) => {
                        const isRegression = row.status === 'regression';
                        const isInsufficient = row.status === 'insufficient_data';
                        const fmtDelta = (v: number | null | undefined, invert = false) => {
                          if (v == null) return <span className="text-muted-foreground">—</span>;
                          const bad = invert ? v > 0 : v < 0;
                          const color = bad ? 'text-destructive' : 'text-green-500';
                          return <span className={color}>{v > 0 ? '+' : ''}{v.toFixed(3)}</span>;
                        };
                        return (
                          <tr key={i} className={`border-b hover:bg-muted/30 ${isRegression ? 'bg-destructive/5' : ''}`}>
                            <td className="p-3 font-medium">{row.languagePair}</td>
                            <td className="p-3 text-muted-foreground">{row.engineName ?? 'aggregated'}</td>
                            <td className="p-3">
                              {isRegression ? (
                                <Badge variant="destructive">Regression ({row.regressions.length})</Badge>
                              ) : isInsufficient ? (
                                <Badge variant="outline" className="text-muted-foreground">Baseline only</Badge>
                              ) : (
                                <Badge variant="secondary" className="text-green-600">OK</Badge>
                              )}
                            </td>
                            <td className="p-3">{fmtDelta(row.deltas?.bleu)}</td>
                            <td className="p-3">{fmtDelta(row.deltas?.comet)}</td>
                            <td className="p-3">{fmtDelta(row.deltas?.chrf)}</td>
                            <td className="p-3">{fmtDelta(row.deltas?.ter, true)}</td>
                            <td className="p-3 text-muted-foreground text-xs">
                              {row.latest ? new Date(row.latest.runDate).toLocaleDateString() : '—'}
                              {row.latest?.notes && <span className="ml-1 opacity-60">({row.latest.notes})</span>}
                            </td>
                            <td className="p-3 text-muted-foreground">{row.latest?.segmentCount ?? '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No regression data available yet. Snapshot at least two runs to start detecting regressions.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Raw snapshot history */}
          {filteredSnapshots.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Snapshot History</CardTitle>
                <CardDescription>All recorded evaluation snapshots, newest first.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Date</th>
                        <th className="p-3 text-left">Language Pair</th>
                        <th className="p-3 text-left">Engine</th>
                        <th className="p-3 text-left">BLEU</th>
                        <th className="p-3 text-left">COMET</th>
                        <th className="p-3 text-left">ChrF</th>
                        <th className="p-3 text-left">TER</th>
                        <th className="p-3 text-left">Segments</th>
                        <th className="p-3 text-left">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...filteredSnapshots]
                        .sort((a, b) => b.runDate.localeCompare(a.runDate))
                        .map((s, i) => (
                          <tr key={i} className="border-b hover:bg-muted/30">
                            <td className="p-3 text-muted-foreground text-xs">{new Date(s.runDate).toLocaleDateString()}</td>
                            <td className="p-3 font-medium">{s.languagePair}</td>
                            <td className="p-3 text-muted-foreground">{s.engineName ?? 'aggregated'}</td>
                            <td className="p-3">{fmtBleu(s.avgBleu)}</td>
                            <td className="p-3">{fmtComet(s.avgComet)}</td>
                            <td className="p-3">{s.avgChrf != null ? s.avgChrf.toFixed(1) : '—'}</td>
                            <td className="p-3">{s.avgTer != null ? s.avgTer.toFixed(1) : '—'}</td>
                            <td className="p-3">{s.segmentCount}</td>
                            <td className="p-3 text-muted-foreground">{s.notes ?? '—'}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── Eval Quality Tab ────────────────────────────────────────────── */}
        <TabsContent value="eval-quality" className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold">Evaluation Quality</h3>
            <p className="text-sm text-muted-foreground">
              Meta-evaluation: how complete and internally consistent is the evaluation data across language pairs?
            </p>
          </div>

          {/* Coverage grid */}
          <Card>
            <CardHeader>
              <CardTitle>Evaluation Signal Coverage</CardTitle>
              <CardDescription>
                % of segments with each signal present per language pair.
                Green ≥ 80% · Yellow 40–79% · Red &lt; 40%
              </CardDescription>
            </CardHeader>
            <CardContent>
              {evalQualityData && evalQualityData.coverage.length > 0 ? (
                <div className="rounded-md border overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Language Pair</th>
                        <th className="p-3 text-left">Total</th>
                        {(['qe_score', 'post_edit', 'bleu', 'comet', 'ter', 'chrf', 'llm_judge'] as const).map(k => (
                          <th key={k} className="p-3 text-left whitespace-nowrap">
                            {k === 'qe_score' ? 'QE Score' : k === 'post_edit' ? 'Post-edit' : k === 'llm_judge' ? 'LLM Judge' : k.toUpperCase()}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {evalQualityData.coverage.map((row, i) => (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{row.language_pair}</td>
                          <td className="p-3 text-muted-foreground">{row.total}</td>
                          {(['qe_score', 'post_edit', 'bleu', 'comet', 'ter', 'chrf', 'llm_judge'] as const).map(k => {
                            const sig = row.signals[k];
                            const color = sig.pct >= 80 ? 'bg-green-500/20 text-green-700 dark:text-green-400'
                                        : sig.pct >= 40 ? 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-400'
                                        : 'bg-red-500/20 text-red-700 dark:text-red-400';
                            return (
                              <td key={k} className="p-3">
                                <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${color}`}>
                                  {sig.pct}%
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p>No segment data available yet.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Per-pair metric correlations */}
          <Card>
            <CardHeader>
              <CardTitle>Metric Correlations by Language Pair</CardTitle>
              <CardDescription>
                Pearson r between automatic metrics per pair. High r between COMET and BLEU is expected for high-resource pairs; low r for CJK/low-resource pairs indicates metric divergence.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {evalQualityData && evalQualityData.correlations_by_pair.length > 0 ? (
                <div className="space-y-4">
                  {evalQualityData.correlations_by_pair.map((pair, i) => (
                    <div key={i}>
                      <p className="text-sm font-medium mb-2">
                        {pair.language_pair} <span className="text-muted-foreground font-normal">n = {pair.n}</span>
                      </p>
                      <div className="rounded-md border">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b bg-muted/50">
                              <th className="p-2 text-left">Metric 1</th>
                              <th className="p-2 text-left">Metric 2</th>
                              <th className="p-2 text-left">r</th>
                              <th className="p-2 text-left">n</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pair.correlations.map((c, j) => (
                              <tr key={j} className="border-b hover:bg-muted/30">
                                <td className="p-2 font-medium">{c.metric1}</td>
                                <td className="p-2 font-medium">{c.metric2}</td>
                                <td className="p-2">
                                  <span className={`font-mono ${Math.abs(c.r) >= 0.7 ? 'text-green-600 dark:text-green-400' : Math.abs(c.r) >= 0.4 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {c.r.toFixed(3)}
                                  </span>
                                </td>
                                <td className="p-2 text-muted-foreground">{c.n}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No post-edited segments with reference metrics yet.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Signal confidence */}
          <Card>
            <CardHeader>
              <CardTitle>Segment Signal Confidence</CardTitle>
              <CardDescription>
                Cross-metric agreement per segment: <code>1 − 2σ</code> over normalized QE·BLEU·COMET·TER·ChrF·LLM signals.
                Green ≥ 70% · Yellow 40–69% · Red &lt; 40% · — = fewer than 2 signals
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {segmentConfidenceData && segmentConfidenceData.scoreable > 0 ? (
                <>
                  {/* Summary row */}
                  <div className="flex gap-6 text-sm">
                    <span className="text-muted-foreground">Total segments: <span className="font-medium text-foreground">{segmentConfidenceData.total}</span></span>
                    <span className="text-muted-foreground">Scoreable (≥ 2 signals): <span className="font-medium text-foreground">{segmentConfidenceData.scoreable}</span></span>
                  </div>

                  {/* Per-pair table */}
                  <div className="rounded-md border overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-3 text-left">Language Pair</th>
                          <th className="p-3 text-left">Segments</th>
                          <th className="p-3 text-left">Scoreable</th>
                          <th className="p-3 text-left">Mean Confidence</th>
                          <th className="p-3 text-left">Min</th>
                          <th className="p-3 text-left">Max</th>
                        </tr>
                      </thead>
                      <tbody>
                        {segmentConfidenceData.by_pair.map((row, i) => {
                          const mc = row.mean_confidence;
                          const color = mc === null ? 'text-muted-foreground'
                            : mc >= 0.7 ? 'text-green-600 dark:text-green-400'
                            : mc >= 0.4 ? 'text-yellow-600 dark:text-yellow-400'
                            : 'text-red-600 dark:text-red-400';
                          return (
                            <tr key={i} className="border-b hover:bg-muted/30">
                              <td className="p-3 font-medium">{row.language_pair}</td>
                              <td className="p-3 text-muted-foreground">{row.count}</td>
                              <td className="p-3 text-muted-foreground">{row.scoreable}</td>
                              <td className={`p-3 font-mono font-medium ${color}`}>
                                {mc !== null ? `${Math.round(mc * 100)}%` : '—'}
                              </td>
                              <td className="p-3 font-mono text-muted-foreground">
                                {row.min_confidence !== null ? `${Math.round(row.min_confidence * 100)}%` : '—'}
                              </td>
                              <td className="p-3 font-mono text-muted-foreground">
                                {row.max_confidence !== null ? `${Math.round(row.max_confidence * 100)}%` : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Low-confidence triage list */}
                  {segmentConfidenceData.lowest_confidence.length > 0 && (
                    <div>
                      <p className="text-sm font-medium mb-2">
                        Lowest-Confidence Segments
                        <span className="ml-2 text-xs font-normal text-muted-foreground">(priority for human review)</span>
                      </p>
                      <div className="rounded-md border overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b bg-muted/50">
                              <th className="p-3 text-left">Pair</th>
                              <th className="p-3 text-left">Confidence</th>
                              <th className="p-3 text-left">Signals</th>
                              <th className="p-3 text-left">Mean Quality</th>
                            </tr>
                          </thead>
                          <tbody>
                            {segmentConfidenceData.lowest_confidence.map((seg, i) => (
                              <tr key={i} className="border-b hover:bg-muted/30">
                                <td className="p-3 text-muted-foreground">{seg.language_pair}</td>
                                <td className="p-3 font-mono font-medium text-red-600 dark:text-red-400">
                                  {seg.confidence !== null ? `${Math.round(seg.confidence * 100)}%` : '—'}
                                </td>
                                <td className="p-3 text-muted-foreground">{seg.n_signals}</td>
                                <td className="p-3 font-mono text-muted-foreground">
                                  {seg.mean_quality !== null ? `${Math.round(seg.mean_quality * 100)}%` : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p>No segments with 2+ signals yet. Run QE and reference metrics to enable confidence scoring.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Judge calibration */}
          <Card>
            <CardHeader>
              <CardTitle>LLM Judge Calibration</CardTitle>
              <CardDescription>
                Pearson r between human post-edit quality (1 − TER) and LLM adequacy score (÷4), per language pair.
                High r = judge is well-calibrated against human effort. Low r = judge diverges from human assessment.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {evalQualityData && evalQualityData.judge_calibration.length > 0 ? (
                <div className="rounded-md border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Language Pair</th>
                        <th className="p-3 text-left">n</th>
                        <th className="p-3 text-left">TER ↔ Adequacy r</th>
                        <th className="p-3 text-left">Calibration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evalQualityData.judge_calibration.map((row, i) => (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="p-3 font-medium">{row.language_pair}</td>
                          <td className="p-3 text-muted-foreground">{row.n}</td>
                          <td className="p-3 font-mono">
                            <span className={Math.abs(row.ter_adequacy_r) >= 0.5 ? 'text-green-600 dark:text-green-400' : Math.abs(row.ter_adequacy_r) >= 0.3 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}>
                              {row.ter_adequacy_r.toFixed(3)}
                            </span>
                          </td>
                          <td className="p-3 text-muted-foreground">{row.interpretation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No paired TER + LLM judge data yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Benchmark tab ──────────────────────────────────────────────── */}
        <TabsContent value="benchmark" className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold">Controlled Engine Benchmark</h3>
            <p className="text-sm text-muted-foreground">
              Run all available MT engines on the same WMT/FLORES reference sentences.
              Metrics are calculated against professional reference translations — results
              are directly comparable across engines.
            </p>
          </div>

          {/* Runner card */}
          <Card>
            <CardHeader>
              <CardTitle>Run Benchmark</CardTitle>
              <CardDescription>
                Translates every sentence in the selected language pair's WMT/FLORES test set
                using each available engine, then computes BLEU, ChrF, TER, and COMET.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-4 items-end">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Language pair</label>
                  <Select value={benchmarkPair} onValueChange={setBenchmarkPair}>
                    <SelectTrigger className="w-36">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(['en-fr', 'fr-en', 'en-jp', 'jp-en', 'en-sw', 'sw-en'] as const).map(p => (
                        <SelectItem key={p} value={p}>{p}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Label (optional)</label>
                  <input
                    className="flex h-9 w-40 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                    placeholder="e.g. baseline"
                    value={benchmarkNotes}
                    onChange={e => setBenchmarkNotes(e.target.value)}
                  />
                </div>
                <Button
                  onClick={async () => {
                    setBenchmarkRunning(true);
                    setBenchmarkError(null);
                    setBenchmarkResult(null);
                    try {
                      const params = new URLSearchParams({ language_pair: benchmarkPair });
                      if (benchmarkNotes) params.set('notes', benchmarkNotes);
                      const res = await fetch(
                        `${API_BASE_URL}/api/wmt/run-multi-engine?${params}`,
                        { method: 'POST' }
                      );
                      if (!res.ok) {
                        const err = await res.json().catch(() => ({ detail: res.statusText }));
                        throw new Error(err.detail || res.statusText);
                      }
                      const data: BenchmarkRunResult = await res.json();
                      setBenchmarkResult(data);
                      // Refresh snapshots so the regression tab also updates
                      fetchSnapshotData();
                    } catch (err: unknown) {
                      setBenchmarkError(err instanceof Error ? err.message : 'Unknown error');
                    } finally {
                      setBenchmarkRunning(false);
                    }
                  }}
                  disabled={benchmarkRunning}
                >
                  {benchmarkRunning ? (
                    <><RefreshCw className="h-4 w-4 mr-2 animate-spin" />Running…</>
                  ) : (
                    'Run benchmark'
                  )}
                </Button>
              </div>

              {benchmarkRunning && (
                <p className="text-sm text-muted-foreground">
                  Translating with all available engines — this may take 1–3 minutes
                  depending on which models are loaded.
                </p>
              )}
              {benchmarkError && (
                <p className="text-sm text-destructive">{benchmarkError}</p>
              )}
            </CardContent>
          </Card>

          {/* Results table */}
          {benchmarkResult && (
            <Card>
              <CardHeader>
                <CardTitle>
                  Results — {benchmarkResult.language_pair}
                  {benchmarkResult.notes && (
                    <span className="ml-2 text-sm font-normal text-muted-foreground">
                      ({benchmarkResult.notes})
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                  {benchmarkResult.n_sentences} reference sentences ·{' '}
                  {benchmarkResult.engines_run} engines ·{' '}
                  {benchmarkResult.comet_available ? 'COMET available' : 'COMET not loaded — install unbabel-comet to enable'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Engine</th>
                        <th className="p-3 text-right">COMET ↑</th>
                        <th className="p-3 text-right">BLEU ↑</th>
                        <th className="p-3 text-right">ChrF ↑</th>
                        <th className="p-3 text-right">TER ↓</th>
                        <th className="p-3 text-right">Segments</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const rows = benchmarkResult.comparison.filter(r => !r.error);
                        const best = (key: keyof BenchmarkEngineResult, higher = true) => {
                          const vals = rows.map(r => r[key] as number | null).filter(v => v != null) as number[];
                          return vals.length ? (higher ? Math.max(...vals) : Math.min(...vals)) : null;
                        };
                        const bestComet = best('comet');
                        const bestBleu  = best('bleu');
                        const bestChrf  = best('chrf');
                        const bestTer   = best('ter', false);

                        const ENGINE_LABELS: Record<string, string> = {
                          opus_fast: 'Helsinki/OPUS',
                          elan_quality: 'ELAN (specialist)',
                          nllb_multilingual: 'NLLB-200',
                          gemini_transcreation: 'Gemini (instructed)',
                          t5_versatile: 'mT5',
                        };

                        return rows.map((row, i) => (
                          <tr key={i} className="border-b hover:bg-muted/30">
                            <td className="p-3 font-medium">
                              {ENGINE_LABELS[row.engine] ?? row.engine}
                            </td>
                            {(['comet', 'bleu', 'chrf'] as const).map(metric => {
                              const val = row[metric] as number | null;
                              const isBest = val !== null && val === (metric === 'comet' ? bestComet : metric === 'bleu' ? bestBleu : bestChrf);
                              return (
                                <td key={metric} className="p-3 text-right">
                                  {val !== null ? (
                                    <span className={isBest ? 'font-bold text-green-600 dark:text-green-400' : ''}>
                                      {metric === 'comet' ? val.toFixed(3) : val.toFixed(1)}
                                    </span>
                                  ) : <span className="text-muted-foreground">—</span>}
                                </td>
                              );
                            })}
                            <td className="p-3 text-right">
                              {row.ter !== null ? (
                                <span className={row.ter === bestTer ? 'font-bold text-green-600 dark:text-green-400' : ''}>
                                  {row.ter.toFixed(1)}
                                </span>
                              ) : <span className="text-muted-foreground">—</span>}
                            </td>
                            <td className="p-3 text-right text-muted-foreground">{row.n_segments}</td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  Bold = best score per metric. COMET is the primary ranking signal (neural metric,
                  higher correlation with human judgment). BLEU favours token overlap with reference —
                  instructed LLMs typically score lower here even when producing better translations.
                </p>
              </CardContent>
            </Card>
          )}

          {/* EvalSnapshot history */}
          <Card>
            <CardHeader>
              <CardTitle>Benchmark History</CardTitle>
              <CardDescription>
                All EvalSnapshots from previous benchmark runs. Use the global language pair and
                engine filters above to narrow results.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {filteredSnapshots.length > 0 ? (
                <div className="rounded-md border overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-3 text-left">Date</th>
                        <th className="p-3 text-left">Language pair</th>
                        <th className="p-3 text-left">Engine</th>
                        <th className="p-3 text-right">COMET</th>
                        <th className="p-3 text-right">BLEU</th>
                        <th className="p-3 text-right">ChrF</th>
                        <th className="p-3 text-right">TER</th>
                        <th className="p-3 text-right">n</th>
                        <th className="p-3 text-left">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSnapshots.map((s, i) => (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="p-3 text-muted-foreground whitespace-nowrap">
                            {new Date(s.runDate).toLocaleDateString()}
                          </td>
                          <td className="p-3 font-mono text-xs">{s.languagePair}</td>
                          <td className="p-3">{s.engineName ?? <span className="text-muted-foreground">aggregated</span>}</td>
                          <td className="p-3 text-right">{fmtComet(s.avgComet)}</td>
                          <td className="p-3 text-right">{fmtBleu(s.avgBleu)}</td>
                          <td className="p-3 text-right">{fmtChrf(s.avgChrf)}</td>
                          <td className="p-3 text-right">{fmtTer(s.avgTer)}</td>
                          <td className="p-3 text-right text-muted-foreground">{s.segmentCount}</td>
                          <td className="p-3 text-muted-foreground text-xs">{s.notes ?? ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No benchmark snapshots yet. Run a benchmark above to populate this table.</p>
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