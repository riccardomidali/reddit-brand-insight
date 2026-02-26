import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, TrendingUp, Sparkles } from "lucide-react";

type Suggestion = {
  text: string;
  score: number;
};

const Explore = () => {
  const [brand, setBrand] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSuggest = async () => {
    const trimmedBrand = brand.trim();
    if (!trimmedBrand) return;

    setSuggestionsLoading(true);
    setSuggestionsError(null);
    setSuggestions([]);

    try {
      const params = new URLSearchParams({
        brand: trimmedBrand,
        subreddit: "all",
      });
      const res = await fetch(`/api/suggest?${params.toString()}`);
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          payload && typeof payload === "object" && "detail" in payload
            ? String((payload as Record<string, unknown>).detail)
            : "Failed to fetch suggestions";
        throw new Error(detail);
      }

      const items = payload && typeof payload === "object" && Array.isArray((payload as Record<string, unknown>).suggestions)
        ? (payload as Record<string, unknown>).suggestions
        : [];

      const normalized = items
        .filter((item): item is Suggestion => {
          if (!item || typeof item !== "object") return false;
          const value = item as Record<string, unknown>;
          return typeof value.text === "string" && typeof value.score === "number";
        })
        .sort((a, b) => b.score - a.score || a.text.localeCompare(b.text))
        .slice(0, 5);

      setSuggestions(normalized);
      if (normalized.length === 0) {
        setSuggestionsError("No suggestions found for this brand.");
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setSuggestionsError(message);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const handleProceed = () => {
    if (!brand.trim()) return;
    const searchParams = new URLSearchParams({ brand });
    if (query.trim()) searchParams.append("query", query);
    navigate(`/dashboard?${searchParams.toString()}`);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-2xl animate-fade-in">
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold mb-3">
            <span className="gradient-text">BrandPulse</span>
          </h1>
          <p className="text-muted-foreground text-lg">
            AI-powered brand sentiment analysis from Reddit
          </p>
        </div>

        <Card className="glass-card rounded-2xl">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-2xl">Brand Explorer</CardTitle>
                <CardDescription>Analyze brand perception and sentiment</CardDescription>
              </div>
              <TrendingUp className="h-8 w-8 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="brand" className="text-base">
                Brand Name
              </Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="brand"
                  placeholder="e.g., Nike, Patagonia"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleProceed()}
                  className="pl-10 h-12 text-base"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="query" className="text-base">
                Query (Optional)
              </Label>
              <Input
                id="query"
                placeholder="e.g., sustainability, innovation"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleProceed()}
                className="h-12 text-base"
              />
            </div>

            <div className="flex gap-3">
              <Button
                onClick={handleSuggest}
                variant="outline"
                disabled={!brand.trim() || suggestionsLoading}
                className="flex-1 h-12"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {suggestionsLoading ? "Finding suggestions..." : "Suggest Queries"}
              </Button>
              <Button
                onClick={handleProceed}
                disabled={!brand.trim()}
                className="flex-1 h-12"
              >
                Proceed to Dashboard
              </Button>
            </div>

            {(suggestionsLoading || suggestionsError || suggestions.length > 0) && (
              <div className="space-y-3 pt-4 border-t animate-fade-in">
                {suggestionsLoading ? (
                  <p className="text-sm text-muted-foreground">Scanning Reddit and building suggestions...</p>
                ) : null}
                {suggestionsError ? (
                  <p className="text-sm text-red-500">{suggestionsError}</p>
                ) : null}
                {suggestions.length > 0 ? (
                  <>
                    <p className="text-sm font-medium text-muted-foreground">Suggested Queries</p>
                    <div className="flex flex-wrap gap-2">
                      {suggestions.map((suggestion) => (
                        <Badge
                          key={suggestion.text}
                          variant="secondary"
                          className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors px-3 py-1.5"
                          onClick={() => handleSuggestionClick(suggestion.text)}
                        >
                          {suggestion.text}
                        </Badge>
                      ))}
                    </div>
                  </>
                ) : null}
                </div>
            )}
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>Try popular brands: Nike, Patagonia, Apple, Tesla</p>
        </div>
      </div>
    </div>
  );
};

export default Explore;
