"use client";

import React from "react";
import {
  Activity,
  Flame,
  Droplets,
  GitBranch,
} from "lucide-react";
import { cn, scoreToPercent } from "@/lib/utils";
import type { TimeScore } from "@/lib/types";

interface TimeScoreCardProps {
  dimension: string;
  data: TimeScore;
}

function scoreStrokeColor(score: number): string {
  if (score >= 0.7) return "#10b981";
  if (score >= 0.4) return "#f59e0b";
  return "#f43f5e";
}

function scoreBgGlow(score: number): string {
  if (score >= 0.7) return "shadow-emerald-500/10";
  if (score >= 0.4) return "shadow-amber-500/10";
  return "shadow-rose-500/10";
}

function scoreTextColor(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-amber-400";
  return "text-rose-400";
}

function scoreBorderColor(score: number): string {
  if (score >= 0.7) return "border-emerald-500/20";
  if (score >= 0.4) return "border-amber-500/20";
  return "border-rose-500/20";
}

const DIMENSION_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode }
> = {
  tissue: {
    label: "Tissue",
    icon: <Activity className="h-3.5 w-3.5" />,
  },
  inflammation: {
    label: "Inflammation",
    icon: <Flame className="h-3.5 w-3.5" />,
  },
  moisture: {
    label: "Moisture",
    icon: <Droplets className="h-3.5 w-3.5" />,
  },
  edge: {
    label: "Edge",
    icon: <GitBranch className="h-3.5 w-3.5" />,
  },
};

// SVG circular gauge
const RADIUS = 36;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function CircularGauge({ score }: { score: number }) {
  const percent = scoreToPercent(score);
  const offset = CIRCUMFERENCE - (percent / 100) * CIRCUMFERENCE;
  const strokeColor = scoreStrokeColor(score);

  return (
    <div className="relative w-[88px] h-[88px] mx-auto">
      <svg
        viewBox="0 0 88 88"
        className="w-full h-full -rotate-90"
      >
        {/* Background track */}
        <circle
          cx="44"
          cy="44"
          r={RADIUS}
          fill="none"
          stroke="hsl(220 25% 18%)"
          strokeWidth="6"
        />
        {/* Progress arc */}
        <circle
          cx="44"
          cy="44"
          r={RADIUS}
          fill="none"
          stroke={strokeColor}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
          style={
            {
              "--gauge-circumference": CIRCUMFERENCE,
              "--gauge-offset": offset,
            } as React.CSSProperties
          }
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn(
            "text-lg font-bold font-mono leading-none",
            scoreTextColor(score)
          )}
        >
          {percent}
        </span>
        <span className="text-[9px] text-muted-foreground/60 mt-0.5">
          / 100
        </span>
      </div>
    </div>
  );
}

export function TimeScoreCard({ dimension, data }: TimeScoreCardProps) {
  const config = DIMENSION_CONFIG[dimension] || {
    label: dimension,
    icon: <Activity className="h-3.5 w-3.5" />,
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card/80 p-4 transition-all duration-200 shadow-lg",
        scoreBorderColor(data.score),
        scoreBgGlow(data.score)
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className={cn("opacity-70", scoreTextColor(data.score))}>
          {config.icon}
        </span>
        <span className="text-xs font-semibold text-foreground">
          {config.label}
        </span>
      </div>

      {/* Circular Gauge */}
      <CircularGauge score={data.score} />

      {/* Label */}
      <p className="text-[10px] text-muted-foreground text-center mt-2 capitalize truncate">
        {data.type}
      </p>
    </div>
  );
}
