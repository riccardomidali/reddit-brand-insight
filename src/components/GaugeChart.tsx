import { useEffect, useState } from "react";

interface GaugeChartProps {
  score: number;
  label: string;
  size?: "sm" | "md" | "lg";
}

const GaugeChart = ({ score, label, size = "md" }: GaugeChartProps) => {
  const [animatedScore, setAnimatedScore] = useState(0);

  const dimensions = {
    sm: { radius: 60, strokeWidth: 8, fontSize: "text-xl" },
    md: { radius: 80, strokeWidth: 10, fontSize: "text-3xl" },
    lg: { radius: 100, strokeWidth: 12, fontSize: "text-4xl" },
  };

  const { radius, strokeWidth, fontSize } = dimensions[size];
  const circumference = Math.PI * radius;
  const viewBox = radius + strokeWidth + 10;

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScore(score);
    }, 100);
    return () => clearTimeout(timer);
  }, [score]);

  const offset = circumference - (animatedScore / 100) * circumference;

  // Calculate gradient color based on score
  const getGradientId = () => `gradient-${label.replace(/\s+/g, "-")}`;

  return (
    <div className="flex flex-col items-center justify-center p-6">
      <svg
        width={viewBox * 2}
        height={viewBox + 20}
        viewBox={`0 0 ${viewBox * 2} ${viewBox + 20}`}
        className="overflow-visible"
      >
        <defs>
          <linearGradient id={getGradientId()} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="hsl(var(--gradient-start))" />
            <stop offset="50%" stopColor="hsl(var(--gradient-mid))" />
            <stop offset="100%" stopColor="hsl(var(--gradient-end))" />
          </linearGradient>
        </defs>

        {/* Background arc */}
        <path
          d={`M ${strokeWidth + 5} ${viewBox} A ${radius} ${radius} 0 0 1 ${viewBox * 2 - strokeWidth - 5} ${viewBox}`}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Animated score arc */}
        <path
          d={`M ${strokeWidth + 5} ${viewBox} A ${radius} ${radius} 0 0 1 ${viewBox * 2 - strokeWidth - 5} ${viewBox}`}
          fill="none"
          stroke={`url(#${getGradientId()})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: "stroke-dashoffset 1.5s ease-out",
          }}
        />

        {/* Score text */}
        <text
          x={viewBox}
          y={viewBox - 10}
          textAnchor="middle"
          className={`${fontSize} font-bold fill-foreground`}
        >
          {animatedScore.toFixed(1)}
        </text>
        <text
          x={viewBox}
          y={viewBox + 15}
          textAnchor="middle"
          className="text-sm fill-muted-foreground"
        >
          %
        </text>
      </svg>

      <p className="mt-4 text-sm font-medium text-muted-foreground text-center">
        {label}
      </p>
    </div>
  );
};

export default GaugeChart;
