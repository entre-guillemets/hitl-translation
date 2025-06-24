// src/components/EngineAnalyticsDashboard.tsx

export const EngineAnalyticsDashboard: React.FC = () => {
    const [analytics, setAnalytics] = useState<any>(null);
    const [loading, setLoading] = useState(true);
  
    useEffect(() => {
      fetchAnalytics();
    }, []);
  
    const fetchAnalytics = async () => {
      try {
        const response = await fetch('http://localhost:8001/api/analytics/engine-preferences');
        const data = await response.json();
        setAnalytics(data);
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setLoading(false);
      }
    };
  
    if (loading || !analytics) return <div>Loading analytics...</div>;
  
    const chartData = Object.entries(analytics.engineCounts).map(([engine, count]) => ({
      engine: engine.charAt(0).toUpperCase() + engine.slice(1),
      count,
      rating: analytics.averageRatings[engine]?.toFixed(1) || 0
    }));
  
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Engine Preference Analytics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="text-center">
                <div className="text-2xl font-bold">{analytics.totalPreferences}</div>
                <div className="text-sm text-muted-foreground">Total Selections</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.keys(analytics.engineCounts).length}
                </div>
                <div className="text-sm text-muted-foreground">Engines Compared</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.keys(analytics.monthlyTrends).length}
                </div>
                <div className="text-sm text-muted-foreground">Months of Data</div>
              </div>
            </div>
            
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="engine" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#8884d8" name="Times Selected" />
                <Bar dataKey="rating" fill="#82ca9d" name="Average Rating" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    );
  };
  