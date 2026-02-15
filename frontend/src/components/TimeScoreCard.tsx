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

function qualitativeLabel(score: number): string {
  if (score >= 0.8) return "Good";
  if (score >= 0.6) return "Fair";
  if (score >= 0.4) return "Moderate";
  if (score >= 0.2) return "Poor";
  return "Critical";
}

function severityBadge(score: number): string {
  if (score >= 0.7) return "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/15";
  if (score >= 0.4) return "bg-orange-500/10 text-orange-400 ring-1 ring-orange-500/15";
  return "bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/15";
}

function severityText(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-orange-400";
  return "text-rose-400";
}

function barColor(score: number): string {
  if (score >= 0.7) return "bg-emerald-400";
  if (score >= 0.4) return "bg-orange-400";
  return "bg-rose-400";
}

const DIMENSION_CONFIG: Record<
  string,
  {
    label: string;
    icon: React.ElementType;
    accent: string;
    iconColor: string;
  }
> = {
  tissue: {
    label: "Tissue",
    icon: Activity,
    accent: "bg-teal-400",
    iconColor: "text-teal-500",
  },
  inflammation: {
    label: "Inflammation",
    icon: Flame,
    accent: "bg-orange-400",
    iconColor: "text-orange-500",
  },
  moisture: {
    label: "Moisture",
    icon: Droplets,
    accent: "bg-sky-400",
    iconColor: "text-sky-500",
  },
  edge: {
    label: "Edge",
    icon: GitBranch,
    accent: "bg-violet-400",
    iconColor: "text-violet-500",
  },
};

export function TimeScoreCard({ dimension, data }: TimeScoreCardProps) {
  const config = DIMENSION_CONFIG[dimension] || {
    label: dimension,
    icon: Activity,
    accent: "bg-slate-400",
    iconColor: "text-muted-foreground",
  };

  const Icon = config.icon;
  const percent = scoreToPercent(data.score);
  const label = qualitativeLabel(data.score);

  return (
    <div className="apple-card overflow-hidden flex">
      {/* Left accent bar */}
      <div className={cn("w-1 shrink-0 rounded-l-xl", config.accent)} />

      <div className="flex-1 p-3 min-w-0">
        {/* Header: icon + label */}
        <div className="flex items-center gap-1.5 mb-1.5">
          <Icon className={cn("h-3.5 w-3.5 shrink-0", config.iconColor)} />
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider truncate">
            {config.label}
          </span>
        </div>

        {/* Score + badge */}
        <div className="flex items-end justify-between mb-2">
          <span className={cn("text-[22px] font-bold tabular-nums leading-none", severityText(data.score))}>
            {percent}
            <span className="text-[10px] font-normal text-muted-foreground/50 ml-0.5">%</span>
          </span>
          <span
            className={cn(
              "text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap",
              severityBadge(data.score),
            )}
          >
            {label}
          </span>
        </div>

        {/* Progress bar */}
        <div className="rounded-full h-1 w-full bg-muted mb-2">
          <div
            className={cn(
              "rounded-full h-1 transition-all duration-700 ease-out",
              barColor(data.score),
            )}
            style={{ width: `${percent}%` }}
          />
        </div>

        {/* Description */}
        <p className="text-[11px] text-muted-foreground leading-relaxed first-letter:uppercase line-clamp-2">
          {data.type.toLowerCase()}
        </p>
      </div>
    </div>
  );
}
