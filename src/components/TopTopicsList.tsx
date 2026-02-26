import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type TopicKeyword = {
  text: string;
  value: number;
};

type Props = {
  title?: string;
  subtitle?: string;
  keywords: TopicKeyword[];
  topN?: number;
  onTopicClick?: (topic: string) => void;
  className?: string;
};

function clamp01(x: number) {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export function TopTopicsList({
  title = "Top Topics",
  subtitle = "Most frequent themes in discussions",
  keywords,
  topN = 5,
  onTopicClick,
  className,
}: Props) {
  const items = React.useMemo(() => {
    const cleaned = (keywords ?? [])
      .filter((k) => k && typeof k.text === "string" && k.text.trim().length > 0)
      .filter((k) => Number.isFinite(k.value) && k.value > 0)
      .map((k) => ({ text: k.text.trim(), value: k.value }));

    cleaned.sort((a, b) => b.value - a.value || a.text.localeCompare(b.text));
    return cleaned.slice(0, topN);
  }, [keywords, topN]);

  const stats = React.useMemo(() => {
    if (!items.length) return { min: 0, max: 0 };
    const values = items.map((x) => x.value);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [items]);

  const denom = Math.max(1e-9, stats.max - stats.min);

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </CardHeader>

      <CardContent className="space-y-3">
        {items.length === 0 ? (
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            No topics available for this query.
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((it, idx) => {
              const norm = clamp01((it.value - stats.min) / denom);
              const fontSize = 14 + norm * 8;
              const opacity = 0.55 + norm * 0.45;
              const barPct = clamp01(it.value / Math.max(1e-9, stats.max)) * 100;

              const row = (
                <div className="flex items-center gap-3">
                  <div className="w-6 text-right text-xs text-muted-foreground tabular-nums">
                    #{idx + 1}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <div
                        className="min-w-0 truncate font-medium"
                        style={{ fontSize, opacity }}
                        title={it.text}
                      >
                        {it.text}
                      </div>

                      <Badge variant="secondary" className="tabular-nums">
                        {it.value}
                      </Badge>
                    </div>

                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary/80"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );

              return (
                <li key={`${it.text}-${idx}`} className="rounded-lg border bg-background p-3">
                  {onTopicClick ? (
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-auto w-full justify-start p-0 hover:bg-transparent"
                      onClick={() => onTopicClick(it.text)}
                    >
                      {row}
                    </Button>
                  ) : (
                    row
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default TopTopicsList;
