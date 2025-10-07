import { TimelinePoint } from "@/types/dashboard";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface TimelineChartProps {
  data: TimelinePoint[];
}

const TimelineChart = ({ data }: TimelineChartProps) => {
  const formattedData = data.map((point) => ({
    ...point,
    displayMonth: new Date(point.month).getFullYear().toString(),
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
            labelFormatter={(label) => label || "Date"}
            formatter={(value: number, name: string) => {
              if (name === "mentions") return [value, "Mentions"];
              if (name === "avgSentiment") return [(value * 100).toFixed(1) + "%", "Avg Sentiment"];
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
