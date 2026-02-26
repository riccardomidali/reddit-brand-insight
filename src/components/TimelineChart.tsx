import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface TimelineChartProps {
  data: Array<{ month: string; mentions: number }>;
}

const TimelineChart = ({ data }: TimelineChartProps) => {
  const formatXAxisLabel = (monthValue: string) => {
    const date = new Date(monthValue);
    if (!Number.isNaN(date.getTime())) {
      const hasMonthPrecision = /^\d{4}-\d{2}(-\d{2})?$/.test(monthValue);
      return hasMonthPrecision
        ? date.toLocaleDateString(undefined, { month: "short", year: "2-digit" })
        : date.getFullYear().toString();
    }
    return monthValue;
  };

  const formatTooltipLabel = (monthValue: string) => {
    const date = new Date(monthValue);
    if (!Number.isNaN(date.getTime())) {
      const hasMonthPrecision = /^\d{4}-\d{2}(-\d{2})?$/.test(monthValue);
      return hasMonthPrecision
        ? date.toLocaleDateString(undefined, { month: "long", year: "numeric" })
        : date.getFullYear().toString();
    }
    return monthValue;
  };

  const safeData = Array.isArray(data) ? data : [];
  const formattedData = safeData
    .filter((point) => typeof point?.month === "string" && Number.isFinite(point?.mentions))
    .map((point) => ({
      ...point,
      displayMonth: formatXAxisLabel(point.month),
      tooltipLabel: formatTooltipLabel(point.month),
    }));

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={formattedData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="hsl(var(--gradient-start))" />
              <stop offset="50%" stopColor="hsl(var(--gradient-mid))" />
              <stop offset="100%" stopColor="hsl(var(--gradient-end))" />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="displayMonth"
            stroke="hsl(var(--muted-foreground))"
            fontSize={12}
            tickLine={false}
            minTickGap={18}
          />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            fontSize={12}
            tickLine={false}
            label={{ value: "Mentions", angle: -90, position: "insideLeft" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            labelFormatter={(_, payload) => {
              if (Array.isArray(payload) && payload[0] && "payload" in payload[0]) {
                const row = payload[0].payload as { tooltipLabel?: string };
                return row.tooltipLabel || "Date";
              }
              return "Date";
            }}
            formatter={(value: number, name: string) => {
              if (name === "mentions") return [value, "Mentions"];
              return [value, name];
            }}
          />
          <Line
            type="monotone"
            dataKey="mentions"
            stroke="url(#lineGradient)"
            strokeWidth={3}
            dot={{ fill: "hsl(var(--primary))", strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimelineChart;
