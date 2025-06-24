"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertTriangle, Download, RefreshCw, TrendingUp } from 'lucide-react';
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
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
// Assuming these are imported correctly from Shadcn UI or a custom index.ts in components/ui
// import { Input, Label, Progress, Textarea } from '@/components/ui/index'; 


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
  avgTer: number;
  count: number;
}

interface ModelPerformanceData {
  leaderboard: ModelLeaderboardEntry[];
  performanceOverTime: PerformanceTimeEntry[];
  modelComparison: ModelComparisonEntry[];
}

interface ModelLeaderboardEntry {
  model: string;
  engineType: string;
  avgBleu: number;
  avgComet: number;
  avgTer: number;
  avgMetricX: number;
  totalTranslations: number;
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
  editTypes: { minor: number; moderate: number; major: number };
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
      {!compact && (
        <div className="p-3 bg-muted rounded-md">
          <h4 className="font-medium text-sm mb-2">Source Text:</h4>
          <p className="text-sm">{sourceText}</p>
        </div>
      )}
      
      <div className="border rounded-md overflow-hidden" style={{ overflowX: 'auto' }}> {/* Added overflowX auto */}
        <ReactDiffViewer
          oldValue={originalMT}
          newValue={humanEdited}
          {...diffConfig}
        />
      </div>
    </div>
  );
};

const TranslatorImpactSummary: React.FC<{ data: TranslatorSummaryEntry[] }> = ({ data }) => {
  return (
    // This grid makes the 4 language pairs spread out, responsive from 1 to 4 columns
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"> 
      {data.map((translator, index) => (
        <Card key={translator.translatorId || index}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              {translator.translatorId || 'Anonymous Translator'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Total Edits:</span>
              <Badge variant="secondary">{translator.totalEdits}</Badge>
            </div>
            <div className="flex justify-between text-sm">
              <span>Avg Improvement:</span>
              <span className="font-medium">
                {(translator.avgImprovementScore * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Edit Distance:</span>
              <span className="font-medium">
                {translator.avgEditDistance.toFixed(1)}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              Languages: {translator.languagePairs.join(', ')}
            </div>
            <div className="flex gap-1 text-xs">
              <Badge variant="outline" className="text-green-600">
                Minor: {translator.editTypes.minor}
              </Badge>
              <Badge variant="outline" className="text-yellow-600">
                Moderate: {translator.editTypes.moderate}
              </Badge>
              <Badge variant="outline" className="text-red-600">
                Major: {translator.editTypes.major}
              </Badge>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

const TranslatorImpactTable: React.FC<{ 
  data: TranslationComparisonEntry[];
  onRowSelect: (comparison: TranslationComparisonEntry) => void;
}> = ({ data, onRowSelect }) => {
  const [filters, setFilters] = useState({
    languagePair: 'all',
    jobId: 'all',
    editType: 'all'
  });
  
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const filteredData = useMemo(() => {
    return data.filter(item => {
      const languageMatch = filters.languagePair === 'all' || item.languagePair === filters.languagePair;
      const jobMatch = filters.jobId === 'all' || item.jobId === filters.jobId;
      const editMatch = filters.editType === 'all' || item.editType === filters.editType;
      return languageMatch && jobMatch && editMatch;
    });
  }, [data, filters]);

  const paginatedData = useMemo(() => {
    const startIndex = currentPage * pageSize;
    return filteredData.slice(startIndex, startIndex + pageSize);
  }, [filteredData, currentPage, pageSize]);

  const uniqueLanguagePairs = [...new Set(data.map(d => d.languagePair))];
  const uniqueJobs = [...new Set(data.map(d => d.jobName))];

  const getEditTypeBadge = (editType: string) => {
    const variants = {
      minor: 'default',
      moderate: 'secondary', 
      major: 'destructive'
    } as const;
    return <Badge variant={variants[editType as keyof typeof variants]}>{editType}</Badge>;
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-4 items-center">
        <Select value={filters.languagePair} onValueChange={(value) => setFilters(prev => ({...prev, languagePair: value}))}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Language Pair" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Language Pairs</SelectItem>
            {uniqueLanguagePairs.map(pair => (
              <SelectItem key={pair} value={pair}>{pair}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filters.jobId} onValueChange={(value) => setFilters(prev => ({...prev, jobId: value}))}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Translation Job" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Jobs</SelectItem>
            {uniqueJobs.map(job => (
              <SelectItem key={job} value={job}>{job}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filters.editType} onValueChange={(value) => setFilters(prev => ({...prev, editType: value}))}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Edit Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="minor">Minor</SelectItem>
            <SelectItem value="moderate">Moderate</SelectItem>
            <SelectItem value="major">Major</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="border rounded-md overflow-x-auto"> {/* Changed overflow-hidden to overflow-x-auto */}
        <table className="min-w-full"> {/* Added min-w-full to allow table to expand */}
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Source Text</th> {/* Added whitespace-nowrap */}
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Language</th>
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Job</th>
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Edit Type</th>
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Improvement</th>
              <th className="text-left p-3 text-sm font-medium whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((item) => (
              <tr key={item.id} className="border-b hover:bg-muted/50">
                <td className="p-3 text-sm max-w-xs truncate">{item.sourceText}</td>
                <td className="p-3 text-sm">{item.languagePair}</td>
                <td className="p-3 text-sm">{item.jobName}</td>
                <td className="p-3">{getEditTypeBadge(item.editType)}</td>
                <td className="p-3 text-sm font-medium">
                  +{(item.improvementScore * 100).toFixed(1)}%
                </td>
                <td className="p-3">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => onRowSelect(item)}
                  >
                    View Diff
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {paginatedData.length === 0 && (
          <div className="text-center text-muted-foreground p-4">
            No translation comparisons found matching filters.
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Showing {currentPage * pageSize + 1}-{Math.min((currentPage + 1) * pageSize, filteredData.length)} of {filteredData.length}
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm"
            disabled={currentPage === 0}
            onClick={() => setCurrentPage(prev => prev - 1)}
          >
            Previous
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            disabled={(currentPage + 1) * pageSize >= filteredData.length}
            onClick={() => setCurrentPage(prev => prev + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
};

// Dashboard Components
const PostEditMetricsByLanguagePair: React.FC<{ data: LanguagePairMetricEntry[] }> = ({ data }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Post-Edit Quality by Language Pair</CardTitle>
        <CardDescription>BLEU, COMET, and TER scores after human post-editing</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={postEditChartConfig} className="min-h-[300px] w-full h-[350px]"> {/* Adjusted height here */}
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              accessibilityLayer
              data={data}
              margin={{
                top: 20, 
                left: 12,
                right: 12,
              }}
            >
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="languagePair"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
              />
              <YAxis /> {/* Added Y-axis for better readability */}
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent hideLabel />}
              />
              <Bar dataKey="avgBleu" fill="var(--color-avgBleu)" radius={8}>
                <LabelList
                  position="top"
                  offset={12}
                  className="fill-foreground"
                  fontSize={12}
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                />
              </Bar>
              <Bar dataKey="avgComet" fill="var(--color-avgComet)" radius={8}>
                <LabelList
                  position="top"
                  offset={12}
                  className="fill-foreground"
                  fontSize={12}
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                />
              </Bar>
              <Bar dataKey="avgTer" fill="var(--color-avgTer)" radius={8}>
                <LabelList
                  position="top"
                  offset={12}
                  className="fill-foreground"
                  fontSize={12}
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      </CardContent>
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 font-medium leading-none">
          Post-editing quality metrics <TrendingUp className="h-4 w-4" />
        </div>
        <div className="leading-none text-muted-foreground">
          Based on {data.reduce((sum, item) => sum + item.count, 0)} post-edited translations
        </div>
      </CardFooter>
    </Card>
  );
};

// 1. Performance Over Time with Area Chart Interactive
const PerformanceOverTime: React.FC<{ data: PerformanceTimeEntry[] }> = ({ data }) => {
  const [selectedMetrics, setSelectedMetrics] = useState(['bleuScore', 'cometScore', 'metricXScore']);
  const [selectedEngines, setSelectedEngines] = useState<string[]>([]);
  const [selectedLanguagePairs, setSelectedLanguagePairs] = useState<string[]>([]);

  const uniqueEngines = [...new Set(data.map(d => d.model))];
  const uniqueLanguagePairs = [...new Set(data.map(d => d.languagePair).filter(Boolean))];

  const filteredData = data.filter(d => {
    const engineMatch = selectedEngines.length === 0 || selectedEngines.includes(d.model);
    const languageMatch = selectedLanguagePairs.length === 0 || selectedLanguagePairs.includes(d.languagePair || '');
    return engineMatch && languageMatch;
  });

  // Transform data for area chart - use requestId as X axis
  const chartData = filteredData.map((item, index) => ({
    request: item.requestId || `Request ${index + 1}`,
    bleuScore: item.bleuScore * 100,
    cometScore: item.cometScore * 100,
    metricXScore: item.metricXScore * 10, // Scale MetricX to be comparable
    terScore: item.terScore ? item.terScore : 0, // TER is already % from backend
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance Over Time</CardTitle>
        <CardDescription>Quality metrics across translation requests</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-4 mb-4">
          <Select onValueChange={(value) => setSelectedEngines(value ? value.split(',') : [])}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All Engines" />
            </SelectTrigger>
            <SelectContent>
              {uniqueEngines.map(engine => (
                <SelectItem key={engine} value={engine}>{engine}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select onValueChange={(value) => setSelectedLanguagePairs(value ? value.split(',') : [])}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All Language Pairs" />
            </SelectTrigger>
            <SelectContent>
              {uniqueLanguagePairs.map(pair => (
                <SelectItem key={pair} value={pair}>{pair}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <ChartContainer config={performanceChartConfig} className="min-h-[300px] w-full h-[350px]"> {/* Adjusted height here */}
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              accessibilityLayer
              data={chartData}
              margin={{
                left: 12,
                right: 12,
              }}
            >
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="request"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                tickFormatter={(value) => value.slice(-3)} // Show last 3 chars of request ID
              />
              <YAxis /> {/* Added Y-axis */}
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent />}
              />
              {selectedMetrics.includes('bleuScore') && (
                <Area
                  dataKey="bleuScore"
                  type="natural"
                  fill="var(--color-bleuScore)"
                  fillOpacity={0.4}
                  stroke="var(--color-bleuScore)"
                  stackId="a" // Use stackId if you want stacked areas, otherwise remove
                />
              )}
              {selectedMetrics.includes('cometScore') && (
                <Area
                  dataKey="cometScore"
                  type="natural"
                  fill="var(--color-cometScore)"
                  fillOpacity={0.4}
                  stroke="var(--color-cometScore)"
                  stackId="a"
                />
              )}
              {selectedMetrics.includes('metricXScore') && (
                <Area
                  dataKey="metricXScore"
                  type="natural"
                  fill="var(--color-metricXScore)"
                  fillOpacity={0.4}
                  stroke="var(--color-metricXScore)"
                  stackId="a"
                />
              )}
               {selectedMetrics.includes('terScore') && (
                <Area
                  dataKey="terScore"
                  type="natural"
                  fill="var(--color-terScore)"
                  fillOpacity={0.4}
                  stroke="var(--color-terScore)"
                  stackId="a"
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </ChartContainer>
      </CardContent>
    </Card>
  );
};

// 2. Engine Preference Analysis with Bar Chart Multiple (Now shows both By Engine and By Language Pair side-by-side)
const EnginePreferenceAnalysis: React.FC<{ data: EnginePreferenceEntry[] }> = ({ data }) => {

  const chartDataByEngine = useMemo(() => {
    return data.reduce((acc, item) => {
      const existing = acc.find(a => a.name === item.engine);
      if (existing) {
        // Correctly average, accounting for existing count
        existing.selections += item.selectionCount;
        existing.avgRating = (existing.avgRating * existing.count + item.avgRating * item.count) / (existing.count + item.count);
        existing.count += item.count;
      } else {
        acc.push({
          name: item.engine,
          selections: item.selectionCount,
          avgRating: item.avgRating * 20, // Scale to make visible alongside selections
          satisfaction: item.overallSatisfaction
        });
      }
      return acc;
    }, [] as any[]).sort((a, b) => b.selections - a.selections); // Sort by selections
  }, [data]);

  const chartDataByLanguagePair = useMemo(() => {
    return data.reduce((acc, item) => {
      const key = item.languagePair;
      const existing = acc.find(a => a.name === key);
      if (existing) {
        existing.selections += item.selectionCount;
        existing.avgRating = (existing.avgRating * existing.count + item.avgRating * item.count) / (existing.count + item.count);
        existing.count += item.count;
      } else {
        acc.push({
          name: key,
          selections: item.selectionCount,
          avgRating: item.avgRating * 20, // Scale to make visible alongside selections
          satisfaction: item.overallSatisfaction
        });
      }
      return acc;
    }, [] as any[]).sort((a, b) => b.selections - a.selections); // Sort by selections
  }, [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Engine Preference Analysis</CardTitle>
        <CardDescription>Selection counts and ratings</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"> {/* Two columns grid */}
          <div>
            <h4 className="text-sm font-medium mb-2">By Engine</h4>
            <ChartContainer config={preferenceChartConfig} className="min-h-[250px] w-full h-[300px]"> {/* Explicit height */}
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  accessibilityLayer
                  data={chartDataByEngine}
                  margin={{ top: 20, left: 12, right: 12 }}
                >
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(value) => value.slice(0, 8)} />
                  <YAxis />
                  <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
                  <Bar dataKey="selections" fill="var(--color-selections)" radius={8}>
                    <LabelList position="top" offset={12} className="fill-foreground" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </div>
          <div>
            <h4 className="text-sm font-medium mb-2">By Language Pair</h4>
            <ChartContainer config={preferenceChartConfig} className="min-h-[250px] w-full h-[300px]"> {/* Explicit height */}
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  accessibilityLayer
                  data={chartDataByLanguagePair}
                  margin={{ top: 20, left: 12, right: 12 }}
                >
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(value) => value.slice(0, 8)} />
                  <YAxis />
                  <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
                  <Bar dataKey="selections" fill="var(--color-selections)" radius={8}>
                    <LabelList position="top" offset={12} className="fill-foreground" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </div>
        </div>
      </CardContent>
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 font-medium leading-none">
          Engine preferences trending <TrendingUp className="h-4 w-4" />
        </div>
        <div className="leading-none text-muted-foreground">
          Showing selection counts and average ratings
        </div>
      </CardFooter>
    </Card>
  );
};

// 3. Processing Time Analysis with Three Bar Charts side-by-side
const ProcessingTimeAnalysis: React.FC<{ data: ProcessingTimeEntry[] }> = ({ data }) => {
  const chartDataByModel = useMemo(() => {
    return data.reduce((acc, item) => {
      const existing = acc.find(a => a.name === item.model);
      if (existing) {
        // Correctly average, accounting for existing count
        existing.avgProcessingTime = (existing.avgProcessingTime * existing.count + item.avgProcessingTime * item.count) / (existing.count + item.count);
        existing.count += item.count;
      } else {
        acc.push({
          name: item.model,
          avgProcessingTime: item.avgProcessingTime,
          count: item.count
        });
      }
      return acc;
    }, [] as any[]).sort((a,b) => b.avgProcessingTime - a.avgProcessingTime);
  }, [data]);

  const chartDataByEngineType = useMemo(() => {
    return data.reduce((acc, item) => {
      const existing = acc.find(a => a.name === item.engineType);
      if (existing) {
        existing.avgProcessingTime = (existing.avgProcessingTime * existing.count + item.avgProcessingTime * item.count) / (existing.count + item.count);
        existing.count += item.count;
      } else {
        acc.push({
          name: item.engineType,
          avgProcessingTime: item.avgProcessingTime,
          count: item.count
        });
      }
      return acc;
    }, [] as any[]).sort((a,b) => b.avgProcessingTime - a.avgProcessingTime);
  }, [data]);

  const chartDataByWordCount = useMemo(() => {
    // Basic aggregation by bucket if your data has it.
    // If 'wordCountBucket' is not reliably populated, this might need more robust bucketing logic.
    const buckets: { [key: string]: { sum: number; count: number } } = {};
    data.forEach(item => {
      const bucket = item.wordCountBucket || 'overall';
      if (!buckets[bucket]) {
        buckets[bucket] = { sum: 0, count: 0 };
      }
      buckets[bucket].sum += item.avgProcessingTime;
      buckets[bucket].count += item.count; // Use item.count if it represents number of strings in that processing entry
    });

    return Object.keys(buckets).map(bucket => ({
      name: bucket,
      avgProcessingTime: buckets[bucket].count > 0 ? buckets[bucket].sum / buckets[bucket].count : 0,
      count: buckets[bucket].count
    })).sort((a,b) => b.avgProcessingTime - a.avgProcessingTime);
  }, [data]);


  const renderChart = (chartData: any[], title: string) => (
    <div>
      <h4 className="text-sm font-medium mb-2">{title}</h4>
      <ChartContainer config={processingChartConfig} className="min-h-[250px] w-full h-[300px]"> {/* Explicit height */}
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            accessibilityLayer
            data={chartData}
            margin={{ top: 20, left: 12, right: 12 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(value) => value.slice(0, 8)} />
            <YAxis />
            <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
            <Bar dataKey="avgProcessingTime" fill="var(--color-avgProcessingTime)" radius={8}>
              <LabelList position="top" offset={12} className="fill-foreground" fontSize={12} formatter={(value: number) => `${value.toFixed(0)}ms`} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Processing Time Analysis</CardTitle>
        <CardDescription>Average processing times by model, engine type, and word count</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4"> {/* Three columns grid */}
          {renderChart(chartDataByModel, "By Model")}
          {renderChart(chartDataByEngineType, "By Engine Type")}
          {renderChart(chartDataByWordCount, "By Word Count")}
        </div>
      </CardContent>
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 font-medium leading-none">
          Processing efficiency metrics <TrendingUp className="h-4 w-4" />
        </div>
        <div className="leading-none text-muted-foreground">
          Average processing time in milliseconds
        </div>
      </CardFooter>
    </Card>
  );
};

// 4. Severity Breakdown with Bar Chart Label
const SeverityBreakdown: React.FC<{ data: SeverityBreakdownEntry[] }> = ({ data }) => {
  const chartData = data.map(item => ({
    severity: item.severity,
    count: item.count,
  })).sort((a, b) => { // Sort by severity level for consistent display
    const order = { 'CRITICAL': 4, 'MAJOR': 3, 'MODERATE': 2, 'MINOR': 1, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3 }; // Adjusted for possible 'MAJOR'/'MINOR'
    // Fallback for missing keys in order map
    const aOrder = order[a.severity.toUpperCase() as keyof typeof order] ?? 0;
    const bOrder = order[b.severity.toUpperCase() as keyof typeof order] ?? 0;
    return bOrder - aOrder;
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Severity Breakdown</CardTitle>
        <CardDescription>Error counts by severity level</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={severityChartConfig} className="min-h-[250px] w-full h-[300px]"> {/* Explicit height */}
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              accessibilityLayer
              data={chartData}
              margin={{ top: 20, left: 12, right: 12 }}
            >
              <CartesianGrid vertical={false} />
              <XAxis dataKey="severity" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis />
              <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={8}>
                <LabelList position="top" offset={12} className="fill-foreground" fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      </CardContent>
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 font-medium leading-none">
          Error severity distribution <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="leading-none text-muted-foreground">
          Total error annotations by severity
        </div>
      </CardFooter>
    </Card>
  );
};

const MultiEngineSelectionTrends: React.FC<{ data: SelectionTrendEntry[] }> = ({ data }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Multi-Engine Selection Trends</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Selection trends data visualization</p>
        {/* Placeholder for actual chart */}
      </CardContent>
    </Card>
  );
};

const EvaluationModeComparison: React.FC<{ data: EvaluationModeEntry[] }> = ({ data }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evaluation Mode Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Evaluation mode comparison visualization</p>
        {/* Placeholder for actual chart */}
      </CardContent>
    </Card>
  );
};

const SystemHealthOverview: React.FC<{ data: SystemHealthEntry[] }> = ({ data }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>System Health Overview</CardTitle>
      </CardHeader>
      <CardContent>
        {data.map((model, index) => (
          <div key={index} className="flex justify-between items-center p-2 border-b">
            <span className="font-medium">{model.model}</span>
            <div className="flex gap-2">
              <Badge variant="outline">{model.totalTranslations} translations</Badge>
              <Badge variant={model.isActive ? "default" : "secondary"}>
                {model.isActive ? "Active" : "Inactive"}
              </Badge>
              <Badge variant="outline">{model.avgProcessingTime.toFixed(0)}ms avg</Badge>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

const ReviewerBehaviorDashboard: React.FC<{ data: ReviewerBehaviorEntry[] }> = ({ data }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reviewer Behavior</CardTitle>
      </CardHeader>
      <CardContent>
        {data.map((behavior, index) => (
          <div key={index} className="flex justify-between items-center p-2 border-b">
            <div>
              <span className="font-medium">{behavior.reviewerExpertise}</span>
              <Badge variant="outline" className="ml-2">{behavior.approvalType}</Badge>
            </div>
            <div className="flex gap-2 text-sm">
              <span>Avg Time: {(behavior.avgTimeToReview / 1000).toFixed(1)}s</span>
              <span>Cognitive Load: {behavior.avgCognitiveLoad.toFixed(1)}</span>
              <span>Count: {behavior.count}</span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

const ModelLeaderboard: React.FC<{ data: ModelLeaderboardEntry[] }> = ({ data }) => {
  const [sortBy, setSortBy] = useState('avgBleu');
  const [filterEngine, setFilterEngine] = useState('all');

  const filteredData = data
    .filter(item => filterEngine === 'all' || item.engineType === filterEngine)
    .sort((a, b) => (b[sortBy as keyof ModelLeaderboardEntry] as number) - (a[sortBy as keyof ModelLeaderboardEntry] as number));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Leaderboard</CardTitle>
        <div className="flex gap-2">
          <Button
            variant={sortBy === 'avgBleu' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSortBy('avgBleu')}
          >
            BLEU Score
          </Button>
          <Button
            variant={sortBy === 'avgComet' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSortBy('avgComet')}
          >
            COMET Score
          </Button>
          <Button
            variant={sortBy === 'avgTer' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSortBy('avgTer')}
          >
            TER Score
          </Button>
          <Button
            variant={sortBy === 'avgMetricX' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSortBy('avgMetricX')}
          >
            MetricX Score
          </Button>
          <Button
            variant={sortBy === 'totalTranslations' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSortBy('totalTranslations')}
          >
            Usage Count
          </Button>
        </div>
        <Select value={filterEngine} onValueChange={setFilterEngine}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by engine" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Engines</SelectItem>
            <SelectItem value="opus_fast">OPUS Fast</SelectItem>
            <SelectItem value="elan_specialist">ELAN Specialist</SelectItem>
            <SelectItem value="t5_versatile">mT5 Versatile</SelectItem> {/* Updated */}
            <SelectItem value="nllb_multilingual">NLLB Multilingual</SelectItem> {/* Updated */}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        {filteredData.map((model, index) => (
          <div key={model.model} className="flex justify-between items-center p-3 border-b">
            <div>
              <span className="font-bold">#{index + 1} {model.model}</span>
              <Badge variant="outline" className="ml-2">{model.engineType}</Badge>
            </div>
            <div className="flex gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">BLEU</span>
                <div className="font-medium">{(model.avgBleu * 100).toFixed(1)}%</div>
                <div className="text-xs text-muted-foreground">
                  ±{((model.confidenceInterval.bleuHigh - model.confidenceInterval.bleuLow) * 50).toFixed(1)}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">COMET</span>
                <div className="font-medium">{(model.avgComet * 100).toFixed(1)}%</div>
                <div className="text-xs text-muted-foreground">
                  ±{((model.confidenceInterval.cometHigh - model.confidenceInterval.cometLow) * 50).toFixed(1)}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">TER</span>
                <div className="font-medium">{(model.avgTer).toFixed(1)}%</div> {/* TER is already % from backend */}
              </div>
              <div>
                <span className="text-muted-foreground">MetricX</span>
                <div className="font-medium">{model.avgMetricX.toFixed(1)}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Translations</span>
                <div className="font-medium">{model.totalTranslations.toLocaleString()}</div>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

const ErrorHeatmap: React.FC<{ data: ErrorHeatmapEntry[] }> = ({ data }) => {
  const models = [...new Set(data.map(d => d.model))];
  const categories = [...new Set(data.map(d => d.category))];

  const heatmapData = models.map(model => {
    const modelData: any = { model };
    categories.forEach(category => {
      const entry = data.find(d => d.model === model && d.category === category);
      modelData[category] = entry ? entry.painIndex : 0;
    });
    return modelData;
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Error Heatmap (Pain Index)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {heatmapData.map(modelData => (
            <div key={modelData.model} className="flex items-center gap-x-2">
              <div className="w-32 text-sm font-medium truncate">
                {modelData.model}
              </div>
              
              <div className="flex gap-x-1">
                {categories.map(category => {
                  const value = modelData[category] as number;
                  const intensity = Math.min(value / 10, 1);
                  
                  const getSeverityClass = (intensity: number) => {
                    if (intensity === 0) return 'bg-muted text-muted-foreground';
                    if (intensity < 0.3) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300';
                    if (intensity < 0.6) return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-300';
                    return 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300';
                  };

                  return (
                    <div
                      key={category}
                      className={`
                        w-12 h-8 flex items-center justify-center text-xs font-medium rounded
                        ${getSeverityClass(intensity)}
                      `}
                    >
                      {value.toFixed(1)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-4 flex items-center gap-x-2">
          <div className="w-32"></div>
          <div className="flex gap-x-1">
            {categories.map(category => (
              <div key={category} className="w-12 text-xs text-center text-muted-foreground truncate">
                {category}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const QualityCorrelationMatrix: React.FC<{ data: CorrelationEntry[] }> = ({ data }) => {
  const metrics = ['BLEU', 'COMET', 'TER', 'METRICX'];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quality Score Correlation Matrix</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-1">
          {metrics.map(metric1 => (
            <div key={metric1} className="flex gap-1 items-center">
              <div className="w-16 text-sm font-medium">{metric1}</div>
              {metrics.map(metric2 => {
                const correlation = data.find(d =>
                  (d.metric1 === metric1 && d.metric2 === metric2) ||
                  (d.metric1 === metric2 && d.metric2 === metric1)
                )?.correlation || (metric1 === metric2 ? 1 : 0);

                const intensity = Math.abs(correlation);
                
                const getCorrelationClass = (correlation: number, intensity: number) => {
                  if (correlation > 0) {
                    if (intensity < 0.3) return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300';
                    if (intensity < 0.7) return 'bg-green-200 text-green-900 dark:bg-green-900/40 dark:text-green-200';
                    return 'bg-green-300 text-green-900 dark:bg-green-900/60 dark:text-green-100';
                  } else {
                    if (intensity < 0.3) return 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300';
                    if (intensity < 0.7) return 'bg-red-200 text-red-900 dark:bg-red-900/40 dark:text-red-200';
                    return 'bg-red-300 text-red-900 dark:bg-red-900/60 dark:text-red-100';
                  }
                };

                return (
                  <div
                    key={metric2}
                    className={`w-16 h-8 flex items-center justify-center text-xs rounded ${getCorrelationClass(correlation, intensity)}`}
                    title={`${metric1} vs ${metric2}: ${correlation.toFixed(2)}`}
                  >
                    {correlation.toFixed(2)}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

// Main Dashboard Component
export const QualityDashboard: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [postEditData, setPostEditData] = useState<PostEditMetricsData | null>(null);
  const [translatorImpactData, setTranslatorImpactData] = useState<TranslatorImpactData | null>(null);
  const [selectedComparison, setSelectedComparison] = useState<TranslationComparisonEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [languagePair, setLanguagePair] = useState('all');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchDashboardData();
    fetchPostEditData();
    fetchTranslatorImpactData();
  }, [languagePair]);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/analytics?languagePair=${languagePair}`);
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPostEditData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/post-edit-metrics?languagePair=${languagePair}`);
      if (response.ok) {
        const data = await response.json();
        setPostEditData(data);
      }
    } catch (error) {
      console.error('Failed to fetch post-edit data:', error);
    }
  };

  const fetchTranslatorImpactData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/translator-impact?languagePair=${languagePair}`);
      if (response.ok) {
        const data = await response.json();
        setTranslatorImpactData(data);
      }
    } catch (error) {
      console.error('Failed to fetch translator impact data:', error);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchDashboardData();
    await fetchPostEditData();
    await fetchTranslatorImpactData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p>Loading dashboard data...</p>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertTriangle className="h-8 w-8 mx-auto mb-4 text-yellow-500" />
          <p>No data available</p>
          <Button onClick={handleRefresh} className="mt-2">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Quality Dashboard</h1>
        <div className="flex gap-4">
          <Select value={languagePair} onValueChange={setLanguagePair}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Language Pair" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Language Pairs</SelectItem>
              <SelectItem value="en-jp">EN → JP</SelectItem>
              <SelectItem value="jp-en">JP → EN</SelectItem>
              <SelectItem value="en-fr">EN → FR</SelectItem>
              <SelectItem value="fr-en">FR → EN</SelectItem>
              <SelectItem value="jp-fr">JP → FR</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Dashboard Content */}
      <Tabs defaultValue="quality" className="w-full">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="performance">🚀 Performance</TabsTrigger>
          <TabsTrigger value="preferences">👍 Preferences</TabsTrigger>
          <TabsTrigger value="annotations">🐛 Annotations</TabsTrigger>
          <TabsTrigger value="multi-engine">⚖️ Multi-Engine</TabsTrigger>
          <TabsTrigger value="quality">🔬 Quality</TabsTrigger>
          <TabsTrigger value="operations">🧰 Operations</TabsTrigger>
          <TabsTrigger value="translator-impact">👨‍💻 Translator Impact</TabsTrigger> {/* Renamed tab */}
        </TabsList>

        <TabsContent value="performance" className="space-y-4">
          <ModelLeaderboard data={dashboardData.modelPerformance.leaderboard} />
          {/* Performance Over Time chart now occupies full width */}
          <PerformanceOverTime data={dashboardData.modelPerformance.performanceOverTime} />
        </TabsContent>

        <TabsContent value="preferences" className="space-y-4">
          {/* Engine Preference Analysis now shows two charts side-by-side */}
          <EnginePreferenceAnalysis data={dashboardData.humanPreferences.enginePreferences} />
          <ReviewerBehaviorDashboard data={dashboardData.humanPreferences.reviewerBehavior} />
        </TabsContent>

        <TabsContent value="annotations" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"> {/* Side-by-side layout */}
            <ErrorHeatmap data={dashboardData.annotations.errorHeatmap} />
            <SeverityBreakdown data={dashboardData.annotations.severityBreakdown} />
          </div>
        </TabsContent>

        <TabsContent value="multi-engine" className="space-y-4">
          <MultiEngineSelectionTrends data={dashboardData.multiEngine.selectionTrends} />
        </TabsContent>

        <TabsContent value="quality" className="space-y-4">
          {postEditData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"> {/* Side-by-side layout */}
              <PostEditMetricsByLanguagePair data={postEditData.languagePairMetrics} />
              <QualityCorrelationMatrix data={postEditData.correlationMatrix} />
            </div>
          )}
          <EvaluationModeComparison data={dashboardData.qualityScores.evaluationModes} />
        </TabsContent>

        <TabsContent value="operations" className="space-y-4">
          {/* Processing Time Analysis now shows three charts side-by-side */}
          <ProcessingTimeAnalysis data={dashboardData.operational.processingTimes} />
          <SystemHealthOverview data={dashboardData.operational.systemHealth} />
        </TabsContent>

        <TabsContent value="translator-impact" className="space-y-6"> {/* Updated tab value */}
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold">Translator Impact Analysis</h3>
              <p className="text-sm text-muted-foreground">
                Compare machine translations with human-edited versions to measure translator impact
              </p>
            </div>
            <Button variant="outline" onClick={fetchTranslatorImpactData}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          {translatorImpactData && (
            <>
              {/* Summary Cards spread across 4 columns, but now use flex-wrap for better responsiveness */}
              <div className="flex flex-wrap justify-center md:justify-start gap-4 mb-6"> 
                <TranslatorImpactSummary data={translatorImpactData.summary} />
              </div>

              {/* Translation Comparisons Table (full width) */}
              <Card>
                <CardHeader>
                  <CardTitle>Translation History</CardTitle>
                  <CardDescription>
                    Browse and compare all MT vs human-edited translations
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <TranslatorImpactTable 
                    data={translatorImpactData.comparisons}
                    onRowSelect={setSelectedComparison}
                  />
                </CardContent>
              </Card>

              {/* Selected Comparison Viewer (Modal - only appears on click) */}
              <Dialog open={!!selectedComparison} onOpenChange={(open) => !open && setSelectedComparison(null)}>
                {/* Max-width set to a larger size, e.g., 6xl or 7xl, and ensure overflow is handled */}
                <DialogContent className="max-w-6xl p-6 overflow-auto"> 
                  <DialogHeader>
                    <DialogTitle>Translation Comparison</DialogTitle>
                    <DialogDescription>
                      {selectedComparison?.languagePair} • {selectedComparison?.jobName} • 
                      Improvement: +{(selectedComparison?.improvementScore ?? 0 * 100).toFixed(1)}%
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
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default QualityDashboard;