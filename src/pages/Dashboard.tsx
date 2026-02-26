import { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import GaugeChart from "@/components/GaugeChart";
import TimelineChart from "@/components/TimelineChart";
import { TopTopicsList } from "@/components/TopTopicsList";
import { ArrowLeft, Calendar, BarChart3, Leaf, Lightbulb } from "lucide-react";

type ApiTimelineYearlyPoint = { year: number; mentions: number };
type ApiTimelineMonthlyPoint = { month: string; mentions: number };
type ApiKeyword = { text: string; value: number };
type ApiScores = {
  overallSentiment: number;
  queryScore: number;
  ecoScore: number;
  innovationScore: number;
};

type AnalyzeResponse = {
  brand: string;
  query: string;
  subreddit: string;
  samplesCount: number;
  overallSentiment: number;
  queryScore: number;
  scores: ApiScores;
  timeline: ApiTimelineYearlyPoint[];
  timelineYearly: ApiTimelineYearlyPoint[];
  timelineMonthly: ApiTimelineMonthlyPoint[];
  topKeywords: ApiKeyword[];
};

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

const devDebug = (label: string, payload: unknown) => {
  if (import.meta.env.DEV) {
    console.debug(`[Dashboard] ${label}`, payload);
  }
};

const parseYearlyTimeline = (value: unknown): ApiTimelineYearlyPoint[] =>
  Array.isArray(value)
    ? value
        .filter((point): point is ApiTimelineYearlyPoint => {
          if (!point || typeof point !== "object") return false;
          const p = point as Record<string, unknown>;
          return isFiniteNumber(p.year) && isFiniteNumber(p.mentions);
        })
        .map((point) => ({ year: point.year, mentions: point.mentions }))
    : [];

const parseMonthlyTimeline = (value: unknown): ApiTimelineMonthlyPoint[] =>
  Array.isArray(value)
    ? value
        .filter((point): point is ApiTimelineMonthlyPoint => {
          if (!point || typeof point !== "object") return false;
          const p = point as Record<string, unknown>;
          return typeof p.month === "string" && isFiniteNumber(p.mentions);
        })
        .map((point) => ({ month: point.month, mentions: point.mentions }))
    : [];

const parseKeywords = (value: unknown): ApiKeyword[] =>
  Array.isArray(value)
    ? value
        .filter((word): word is ApiKeyword => {
          if (!word || typeof word !== "object") return false;
          const w = word as Record<string, unknown>;
          return typeof w.text === "string" && isFiniteNumber(w.value);
        })
        .map((word) => ({ text: word.text, value: word.value }))
    : [];

const normalizeAnalyzeResponse = (raw: unknown): AnalyzeResponse | null => {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  const rawScores =
    value.scores && typeof value.scores === "object"
      ? (value.scores as Record<string, unknown>)
      : null;

  const overallSentiment = isFiniteNumber(value.overallSentiment)
    ? value.overallSentiment
    : rawScores && isFiniteNumber(rawScores.overallSentiment)
      ? rawScores.overallSentiment
      : NaN;

  if (
    typeof value.brand !== "string" ||
    typeof value.query !== "string" ||
    typeof value.subreddit !== "string" ||
    !isFiniteNumber(value.samplesCount) ||
    !isFiniteNumber(overallSentiment)
  ) {
    return null;
  }

  const queryScore = isFiniteNumber(value.queryScore)
    ? value.queryScore
    : rawScores && isFiniteNumber(rawScores.queryScore)
      ? rawScores.queryScore
      : overallSentiment;

  const ecoScore =
    rawScores && isFiniteNumber(rawScores.ecoScore) ? rawScores.ecoScore : NaN;
  const innovationScore =
    rawScores && isFiniteNumber(rawScores.innovationScore)
      ? rawScores.innovationScore
      : NaN;

  const timelineYearly = parseYearlyTimeline(value.timelineYearly ?? value.timeline);
  const timelineMonthly = parseMonthlyTimeline(value.timelineMonthly);
  const topKeywords = parseKeywords(value.topKeywords);

  return {
    brand: value.brand,
    query: value.query,
    subreddit: value.subreddit,
    samplesCount: value.samplesCount,
    overallSentiment,
    queryScore,
    scores: {
      overallSentiment,
      queryScore,
      ecoScore,
      innovationScore,
    },
    timeline: timelineYearly,
    timelineYearly,
    timelineMonthly,
    topKeywords,
  };
};

export default function Dashboard() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const brand = searchParams.get("brand") || "";
  const query = searchParams.get("query") || "";
  const subreddit = searchParams.get("subreddit") || "all";
  const limitPosts = Number(searchParams.get("limit_posts") || 50);

  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const url = useMemo(() => {
    const sp = new URLSearchParams();
    sp.set("brand", brand);
    sp.set("query", query);
    sp.set("subreddit", subreddit);
    sp.set("limit_posts", String(limitPosts));
    return `/api/analyze?${sp.toString()}`;
  }, [brand, query, subreddit, limitPosts]);

  useEffect(() => {
    if (!brand) return;

    setLoading(true);
    setErr(null);
    setData(null);

    devDebug("request url", url);

    fetch(url)
      .then(async (r) => {
        devDebug("response status", r.status);
        const text = await r.text();
        if (!r.ok) {
          throw new Error(`Request failed (${r.status}): ${text || "unknown error"}`);
        }
        return text ? JSON.parse(text) : null;
      })
      .then((json: unknown) => {
        devDebug("response payload", json);
        const normalized = normalizeAnalyzeResponse(json);
        if (!normalized) {
          throw new Error("Unexpected API response shape. Required fields are missing or invalid.");
        }
        setData(normalized);
      })
      .catch((e: unknown) => {
        const message = e instanceof Error ? e.message : String(e);
        setErr(message);
        devDebug("request error", message);
      })
      .finally(() => setLoading(false));
  }, [brand, url]);

  if (!brand) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold">Missing brand</p>
          <Link to="/"><Button variant="outline">Back</Button></Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (err) {
    return (
      <div className="min-h-screen p-4 md:p-8">
        <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
          <Link to="/">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Explore
            </Button>
          </Link>
          <Card className="glass-card rounded-2xl border-red-500/40">
            <CardHeader>
              <CardTitle>Dashboard unavailable</CardTitle>
              <CardDescription>
                Could not render analytics for "{brand}". Check the details below.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-red-500">{err}</p>
              <p className="text-sm text-muted-foreground">
                If this happens with a 200 response, verify the response JSON fields expected by the dashboard.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const timelineForChart =
    data.timelineMonthly.length > 0
      ? data.timelineMonthly.map((point) => ({
          month: `${point.month}-01`,
          mentions: point.mentions,
        }))
      : data.timelineYearly.map((point) => ({
          month: String(point.year),
          mentions: point.mentions,
        }));

  const timelineDescription =
    data.timelineMonthly.length > 0
      ? "Mentions per month (last 24 months)"
      : "Mentions per year (sample-based)";
  const safeKeywords = Array.isArray(data.topKeywords) ? data.topKeywords : [];
  const hasTimeline = timelineForChart.length > 0;

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

            <div className="flex flex-wrap items-center gap-2 mt-3">
              {data.query ? <Badge variant="outline">Query: {data.query}</Badge> : null}
              <Badge variant="secondary">{data.samplesCount.toLocaleString()} samples</Badge>
              <Badge variant="secondary">r/{data.subreddit}</Badge>
            </div>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Query Score */}
          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Query Score
              </CardTitle>
              <CardDescription>
                Relevance and sentiment for "{data.query || data.brand}"
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isFiniteNumber(data.scores.queryScore) ? (
                <GaugeChart score={data.scores.queryScore} label="Query Score" size="lg" />
              ) : (
                <p className="text-sm text-muted-foreground">Query score unavailable.</p>
              )}
            </CardContent>
          </Card>

          {/* Overall Sentiment */}
          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Overall Sentiment
              </CardTitle>
              <CardDescription>Aggregate brand perception score</CardDescription>
            </CardHeader>
            <CardContent>
              {isFiniteNumber(data.scores.overallSentiment) ? (
                <GaugeChart score={data.scores.overallSentiment} label="Overall Sentiment" size="lg" />
              ) : (
                <p className="text-sm text-muted-foreground">Overall sentiment unavailable.</p>
              )}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card className="glass-card rounded-2xl lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                Brand Mentions Timeline
              </CardTitle>
              <CardDescription>{timelineDescription}</CardDescription>
            </CardHeader>
            <CardContent>
              {hasTimeline ? (
                <TimelineChart data={timelineForChart} />
              ) : (
                <p className="text-sm text-muted-foreground">No timeline data available for this request.</p>
              )}
            </CardContent>
          </Card>

          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Leaf className="h-5 w-5 text-green-600" />
                Eco-Sustainability
              </CardTitle>
              <CardDescription>Topic relevance across sustainability discussions</CardDescription>
            </CardHeader>
            <CardContent>
              {isFiniteNumber(data.scores.ecoScore) ? (
                <GaugeChart score={data.scores.ecoScore} label="Eco Score" size="md" />
              ) : (
                <p className="text-sm text-muted-foreground">Eco score unavailable.</p>
              )}
            </CardContent>
          </Card>

          <Card className="glass-card rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-yellow-600" />
                Innovation
              </CardTitle>
              <CardDescription>Topic relevance across product and technology discussions</CardDescription>
            </CardHeader>
            <CardContent>
              {isFiniteNumber(data.scores.innovationScore) ? (
                <GaugeChart score={data.scores.innovationScore} label="Innovation Score" size="md" />
              ) : (
                <p className="text-sm text-muted-foreground">Innovation score unavailable.</p>
              )}
            </CardContent>
          </Card>

          <TopTopicsList
            className="glass-card rounded-2xl lg:col-span-2"
            title="Top Topics"
            subtitle="Most frequent themes in brand discussions"
            keywords={safeKeywords}
            topN={5}
            onTopicClick={(topic) => {
              const params = new URLSearchParams();
              params.set("brand", brand);
              params.set("query", topic);
              navigate(`/dashboard?${params.toString()}`);
            }}
          />
        </div>
      </div>
    </div>
  );
}
