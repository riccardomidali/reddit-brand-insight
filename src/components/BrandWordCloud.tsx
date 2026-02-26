import ReactWordcloud from "react-wordcloud";
import { WordCloudItem } from "@/types/dashboard";

interface BrandWordCloudProps {
  words: WordCloudItem[];
}

const BrandWordCloud = ({ words }: BrandWordCloudProps) => {
  const safeWords = Array.isArray(words)
    ? words.filter((word) => typeof word?.text === "string" && Number.isFinite(word?.value))
    : [];

  const options = {
    rotations: 2,
    rotationAngles: [0, 90] as [number, number],
    fontSizes: [16, 64] as [number, number],
    padding: 4,
    colors: [
      "hsl(351, 100%, 65%)",
      "hsl(250, 58%, 62%)",
      "hsl(207, 100%, 56%)",
      "hsl(173, 58%, 39%)",
      "hsl(43, 74%, 66%)",
    ],
    enableTooltip: true,
    deterministic: true,
    fontFamily: "inherit",
    fontWeight: "bold",
    scale: "sqrt" as const,
  };

  return (
    <div className="w-full h-[300px] flex items-center justify-center">
      <ReactWordcloud words={safeWords} options={options} />
    </div>
  );
};

export default BrandWordCloud;
