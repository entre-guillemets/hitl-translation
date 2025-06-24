// src/pages/rlhf-dashboard/RLHFDashboard.tsx

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { RefreshCw, Star, Target, TrendingUp, Users } from 'lucide-react';
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
  const [isTraining, setIsTraining] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/rlhf/analytics');
      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      }
    } catch (error) {
      console.error('Failed to fetch RLHF analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const triggerTraining = async () => {
    setIsTraining(true);
    try {
      const response = await fetch('http://localhost:8001/api/rlhf/train-reward-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_retrain: true })
      });
      
      if (response.ok) {
        alert('Reward model training started successfully!');
        await fetchAnalytics(); // Refresh data
      }
    } catch (error) {
      console.error('Failed to start training:', error);
      alert('Failed to start training');
    } finally {
      setIsTraining(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">RLHF Dashboard</h1>
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
          <h1 className="text-3xl font-bold">RLHF Dashboard</h1>
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
        <h1 className="text-3xl font-bold">RLHF Dashboard</h1>
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
            <CardTitle className="text-sm font-medium">Training Ready</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${analytics.training_data_available ? 'text-green-600' : 'text-red-600'}`}>
              {analytics.training_data_available ? 'Yes' : 'No'}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.training_data_available ? 'Ready to train' : 'Need more data'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Model Status</CardTitle>
            <Star className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Button 
              onClick={triggerTraining}
              disabled={isTraining || !analytics.training_data_available}
              className="w-full"
            >
              {isTraining ? 'Training...' : 'Train Reward Model'}
            </Button>
            {isTraining && (
              <Progress value={50} className="mt-2" />
            )}
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

      {/* RLHF Insights Panel */}
      <Card>
        <CardHeader>
          <CardTitle>Reinforcement Learning from Human Feedback Insights</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-2">
                🎯 Human Preference Learning
              </h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                Every quality rating and preference comparison in Translation QA trains the reward model to better predict human preferences
              </p>
            </div>
            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <h4 className="font-semibold text-green-800 dark:text-green-200 mb-2">
                📈 Continuous Improvement
              </h4>
              <p className="text-sm text-green-700 dark:text-green-300">
                The reward model learns from your feedback patterns to provide increasingly accurate quality predictions
              </p>
            </div>
            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <h4 className="font-semibold text-purple-800 dark:text-purple-200 mb-2">
                🔄 Feedback Loop
              </h4>
              <p className="text-sm text-purple-700 dark:text-purple-300">
                Quality ratings, preference comparisons, and annotations create training data that improves translation quality over time
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
