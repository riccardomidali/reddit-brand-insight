import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getMockSuggestions } from "@/lib/mockData";
import { Search, TrendingUp, Sparkles } from "lucide-react";

const Explore = () => {
  const [brand, setBrand] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Array<{ text: string; relevance: number }>>([]);
  const navigate = useNavigate();

  const handleSuggest = () => {
    if (!brand.trim()) return;
    const mockSuggestions = getMockSuggestions(brand);
    setSuggestions(mockSuggestions);
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
                disabled={!brand.trim()}
                className="flex-1 h-12"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Suggest Queries
              </Button>
              <Button
                onClick={handleProceed}
                disabled={!brand.trim()}
                className="flex-1 h-12"
              >
                Proceed to Dashboard
              </Button>
            </div>

            {suggestions.length > 0 && (
              <div className="space-y-3 pt-4 border-t animate-fade-in">
                <p className="text-sm font-medium text-muted-foreground">
                  Suggested Queries
                </p>
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
