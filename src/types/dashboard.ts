export interface BrandScores {
  queryScore?: number;
  overallSentiment: number;
  eco: number;
  innovation: number;
}

export interface TimelinePoint {
  month: string;
  mentions: number;
  avgSentiment: number;
}

export interface WordCloudItem {
  text: string;
  value: number;
}

export interface RedditPost {
  id: string;
  title: string;
  text: string;
  upvotes: number;
  num_comments: number;
  timestamp: string;
  subreddit: string;
  permalink: string;
}

export interface DashboardData {
  brand: string;
  query?: string;
  scores: BrandScores;
  timeline: TimelinePoint[];
  wordCloud: WordCloudItem[];
  sampleSize: number;
}

export interface SuggestedQuery {
  text: string;
  relevance: number;
}
