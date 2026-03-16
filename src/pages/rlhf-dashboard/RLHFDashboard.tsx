// src/pages/rlhf-dashboard/RLHFDashboard.tsx

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RefreshCw, Target, TrendingUp, Users } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface RLHFAnalytics {
  total_feedback_entries: number;
  total_preference_pairs: number;
  feedback_types: Record<string, number>;
  average_quality_scores: Record<string, number>;
  training_data_available: boolean;
}

export const RLHFDashboard: React.FC = () => {
  const [analytics, setAnalytics] = useState<RLHFAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      // Corrected URL to match backend's combined path
      const response = await fetch('http://localhost:8001/api/analytics/rlhf/analytics');
      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      } else {
        console.error('Failed to fetch RLHF analytics:', response.status, await response.text());
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to fetch RLHF analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Human Preference Data</h1>
        </div>
        <Card>
          <CardContent className="text-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
            <p>Loading RLHF analytics...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Human Preference Data</h1>
        </div>
        <Card>
          <CardContent className="text-center py-8">
            <p className="text-muted-foreground">Failed to load analytics</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const feedbackChartData = Object.entries(analytics.feedback_types).map(([type, count]) => ({
    type,
    count
  }));

  const qualityChartData = Object.entries(analytics.average_quality_scores).map(([type, score]) => ({
    type,
    score: (score * 100).toFixed(1)
  }));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Human Preference Data</h1>
        <Button onClick={fetchAnalytics} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Feedback</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics.total_feedback_entries}</div>
            <p className="text-xs text-muted-foreground">Human feedback entries</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Preference Pairs</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics.total_preference_pairs}</div>
            <p className="text-xs text-muted-foreground">Comparison pairs</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Has Feedback</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${analytics.training_data_available ? 'text-green-600' : 'text-muted-foreground'}`}>
              {analytics.training_data_available ? 'Yes' : 'No'}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.training_data_available ? 'Preference data recorded' : 'No feedback yet'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Fine-Tuning Data</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${analytics.training_data_available ? 'text-green-600' : 'text-yellow-600'}`}>
              {analytics.training_data_available ? 'Available' : 'Building'}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.training_data_available
                ? 'Preference pairs exportable for DPO/SFT'
                : 'Collect more preference pairs'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Feedback Types Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={feedbackChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="type" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Average Quality Scores by Type</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={qualityChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="type" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="score" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Data methodology panel */}
      <Card>
        <CardHeader>
          <CardTitle>About This Data</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-2">What is collected</h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                Engine selection decisions, star ratings, preference reasons, and overall satisfaction scores — one record per reviewed string.
              </p>
            </div>
            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <h4 className="font-semibold text-green-800 dark:text-green-200 mb-2">How it could be used</h4>
              <p className="text-sm text-green-700 dark:text-green-300">
                Preference pairs (chosen vs. rejected engine output) are the correct format for DPO or SFT fine-tuning of local MarianMT/ELAN models via HuggingFace TRL.
              </p>
            </div>
            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <h4 className="font-semibold text-purple-800 dark:text-purple-200 mb-2">Current status</h4>
              <p className="text-sm text-purple-700 dark:text-purple-300">
                Data collection only. Fine-tuning pipelines are out of scope for this platform — sufficient volume (&gt;500 pairs per language pair) and a GPU training environment are required.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};