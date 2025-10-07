import { DashboardData, SuggestedQuery } from "@/types/dashboard";

export const getMockDashboardData = (brand: string, query?: string): DashboardData => {
  const isNike = brand.toLowerCase().includes("nike");
  const isPatagonia = brand.toLowerCase().includes("patagonia");

  if (isPatagonia) {
    return {
      brand: "Patagonia",
      query: query || undefined,
      scores: {
        queryScore: query ? 76.2 : undefined,
        overallSentiment: 72.3,
        eco: 81.4,
        innovation: 63.2,
      },
      timeline: [
        { month: "2023-09", mentions: 112, avgSentiment: 0.21 },
        { month: "2023-10", mentions: 95, avgSentiment: 0.18 },
        { month: "2023-11", mentions: 134, avgSentiment: 0.25 },
        { month: "2023-12", mentions: 156, avgSentiment: 0.29 },
        { month: "2024-01", mentions: 178, avgSentiment: 0.31 },
        { month: "2024-02", mentions: 145, avgSentiment: 0.27 },
        { month: "2024-03", mentions: 167, avgSentiment: 0.22 },
        { month: "2024-04", mentions: 189, avgSentiment: 0.24 },
        { month: "2024-05", mentions: 201, avgSentiment: 0.26 },
        { month: "2024-06", mentions: 215, avgSentiment: 0.28 },
        { month: "2024-07", mentions: 198, avgSentiment: 0.23 },
        { month: "2024-08", mentions: 223, avgSentiment: 0.25 },
      ],
      wordCloud: [
        { text: "sustainable", value: 61 },
        { text: "durable", value: 42 },
        { text: "quality", value: 38 },
        { text: "waterproof", value: 35 },
        { text: "repair", value: 31 },
        { text: "environment", value: 28 },
        { text: "ethical", value: 26 },
        { text: "lifetime", value: 24 },
        { text: "outdoor", value: 22 },
        { text: "responsible", value: 20 },
        { text: "organic", value: 18 },
        { text: "recycled", value: 17 },
        { text: "warranty", value: 16 },
        { text: "comfortable", value: 15 },
        { text: "technical", value: 14 },
      ],
      sampleSize: 3482,
    };
  }

  if (isNike) {
    return {
      brand: "Nike",
      query: query || undefined,
      scores: {
        queryScore: query ? 68.5 : undefined,
        overallSentiment: 65.8,
        eco: 42.1,
        innovation: 78.9,
      },
      timeline: [
        { month: "2023-09", mentions: 542, avgSentiment: 0.15 },
        { month: "2023-10", mentions: 478, avgSentiment: 0.12 },
        { month: "2023-11", mentions: 612, avgSentiment: 0.18 },
        { month: "2023-12", mentions: 689, avgSentiment: 0.21 },
        { month: "2024-01", mentions: 734, avgSentiment: 0.16 },
        { month: "2024-02", mentions: 591, avgSentiment: 0.14 },
        { month: "2024-03", mentions: 645, avgSentiment: 0.17 },
        { month: "2024-04", mentions: 712, avgSentiment: 0.19 },
        { month: "2024-05", mentions: 798, avgSentiment: 0.22 },
        { month: "2024-06", mentions: 823, avgSentiment: 0.18 },
        { month: "2024-07", mentions: 756, avgSentiment: 0.15 },
        { month: "2024-08", mentions: 891, avgSentiment: 0.20 },
      ],
      wordCloud: [
        { text: "performance", value: 78 },
        { text: "design", value: 65 },
        { text: "comfort", value: 58 },
        { text: "innovation", value: 52 },
        { text: "style", value: 49 },
        { text: "quality", value: 45 },
        { text: "technology", value: 42 },
        { text: "athletic", value: 38 },
        { text: "versatile", value: 35 },
        { text: "iconic", value: 32 },
        { text: "lightweight", value: 29 },
        { text: "responsive", value: 27 },
        { text: "breathable", value: 25 },
        { text: "durable", value: 23 },
        { text: "modern", value: 21 },
      ],
      sampleSize: 8247,
    };
  }

  // Default generic brand
  return {
    brand,
    query: query || undefined,
    scores: {
      queryScore: query ? 60.0 : undefined,
      overallSentiment: 55.2,
      eco: 48.5,
      innovation: 52.3,
    },
    timeline: Array.from({ length: 12 }, (_, i) => {
      const date = new Date(2023, 8 + i, 1);
      const month = date.toLocaleDateString("en-US", { year: "numeric", month: "2-digit" });
      return {
        month,
        mentions: Math.floor(Math.random() * 200) + 50,
        avgSentiment: Math.random() * 0.4 - 0.1,
      };
    }),
    wordCloud: [
      { text: "quality", value: 45 },
      { text: "price", value: 38 },
      { text: "recommend", value: 35 },
      { text: "product", value: 32 },
      { text: "service", value: 28 },
      { text: "experience", value: 25 },
      { text: "value", value: 22 },
      { text: "reliable", value: 20 },
    ],
    sampleSize: 1523,
  };
};

export const getMockSuggestions = (brand: string): SuggestedQuery[] => {
  const isNike = brand.toLowerCase().includes("nike");
  const isPatagonia = brand.toLowerCase().includes("patagonia");

  if (isPatagonia) {
    return [
      { text: "sustainability", relevance: 0.92 },
      { text: "waterproof", relevance: 0.85 },
      { text: "repair program", relevance: 0.78 },
      { text: "fleece jackets", relevance: 0.71 },
      { text: "environmental activism", relevance: 0.68 },
      { text: "fair trade", relevance: 0.64 },
    ];
  }

  if (isNike) {
    return [
      { text: "Air Max", relevance: 0.88 },
      { text: "running shoes", relevance: 0.84 },
      { text: "sustainability initiatives", relevance: 0.76 },
      { text: "athlete collaborations", relevance: 0.72 },
      { text: "innovation", relevance: 0.69 },
      { text: "Jordan brand", relevance: 0.65 },
    ];
  }

  return [
    { text: "quality", relevance: 0.75 },
    { text: "customer service", relevance: 0.68 },
    { text: "value for money", relevance: 0.62 },
    { text: "durability", relevance: 0.58 },
  ];
};
