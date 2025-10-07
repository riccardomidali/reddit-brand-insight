import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import GaugeChart from "@/components/GaugeChart";
import TimelineChart from "@/components/TimelineChart";
import BrandWordCloud from "@/components/BrandWordCloud";
import { getMockDashboardData } from "@/lib/mockData";
import { DashboardData } from "@/types/dashboard";
import { ArrowLeft, Calendar, BarChart3, Cloud, Leaf, Lightbulb } from "lucide-react";

const Dashboard = () => {
  const [searchParams] = useSearchParams();
  const brand = searchParams.get("brand") || "";
  const query = searchParams.get("query") || "";
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    if (brand) {
      // Simulate API call
      setTimeout(() => {
        const mockData = getMockDashboardData(brand, query);
        setData(mockData);
      }, 500);
    }
  }, [brand, query]);

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const timelineData = data.timeline.map(point => ({
    ...point,
    displayMonth: new Date(point.month).toLocaleDateString("en-US", { month: "short" }).toUpperCase()
  }));

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Link to="/">
              <Button variant="ghost" size="sm" className="mb-2">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Explore
              </Button>
            </Link>
            <h1 className="text-4xl font-bold">
              <span className="gradient-text">{data.brand}</span> Analytics
            </h1>
            {data.query && (
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className="text-sm">
                  Query: {data.query}
                </Badge>
                <Badge variant="secondary" className="text-sm">
                  {data.sampleSize.toLocaleString()} samples
                </Badge>
              </div>
            )}
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Query Score (if query provided) */}
          {data.scores.queryScore !== undefined && (
            <Card className="glass-card rounded-2xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  Query Score
                </CardTitle>
                <CardDescription>
                  Relevance and sentiment for "{data.query}"
                </CardDescription>
              </CardHeader>
              <CardContent>
                <GaugeChart score={data.scores.queryScore} label="Query Score" size="lg" />
              </CardContent>
            </Card>
          )}

          {/* Overall Sentiment */}
          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Overall Sentiment
              </CardTitle>
              <CardDescription>
                Aggregate brand perception score
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GaugeChart
                score={data.scores.overallSentiment}
                label="Overall Sentiment"
                size={data.scores.queryScore !== undefined ? "lg" : "lg"}
              />
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card className="glass-card rounded-2xl lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                Brand Mentions Timeline
              </CardTitle>
              <CardDescription>
                Reddit mentions over the past 12 months
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TimelineChart data={data.timeline} />
            </CardContent>
          </Card>

          {/* Eco Sustainability Score */}
          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Leaf className="h-5 w-5 text-green-600" />
                Eco-Sustainability
              </CardTitle>
              <CardDescription>
                Environmental and sustainability perception
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GaugeChart score={data.scores.eco} label="Eco Score" size="md" />
            </CardContent>
          </Card>

          {/* Innovation Score */}
          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-yellow-600" />
                Innovation
              </CardTitle>
              <CardDescription>
                Technology and innovation perception
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GaugeChart score={data.scores.innovation} label="Innovation Score" size="md" />
            </CardContent>
          </Card>

          {/* Word Cloud */}
          <Card className="glass-card rounded-2xl lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cloud className="h-5 w-5 text-primary" />
                Top Keywords
              </CardTitle>
              <CardDescription>
                Most frequent words in brand discussions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BrandWordCloud words={data.wordCloud} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
