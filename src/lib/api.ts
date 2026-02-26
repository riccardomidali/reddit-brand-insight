export interface AnalyzeResponse {
  brand: string;
  query: string;
  subreddit: string;
  samplesCount: number;
  overallSentiment: number;
  queryScore: number;
  scores?: {
    overallSentiment: number;
    queryScore: number;
    ecoScore: number;
    innovationScore: number;
  };
  timeline: { year: number; mentions: number }[];
  timelineYearly?: { year: number; mentions: number }[];
  timelineMonthly?: { month: string; mentions: number }[];
  topKeywords: { text: string; value: number }[];
}

export async function analyzeBrand(
  brand: string,
  query?: string,
  subreddit = "all"
): Promise<AnalyzeResponse> {
  const params = new URLSearchParams({
    brand,
    subreddit,
    limit_posts: "100",
  });

  if (query) {
    params.append("query", query);
  }

  const res = await fetch(`/api/analyze?${params.toString()}`);

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "API error");
  }

  return res.json();
}

export interface SuggestResponse {
  brand: string;
  subreddit: string;
  suggestions: { text: string; score: number }[];
}

export async function suggestQueries(
  brand: string,
  subreddit = "all"
): Promise<SuggestResponse> {
  const params = new URLSearchParams({
    brand,
    subreddit,
  });
  const res = await fetch(`/api/suggest?${params.toString()}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Unable to suggest queries");
  }
  return res.json();
}
