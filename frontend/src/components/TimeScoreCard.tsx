"use client";

import React from "react";
import {
  Activity,
  Flame,
  Droplets,
  GitBranch,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimeScore } from "@/lib/types";

interface TimeScoreCardProps {
  dimension: string;
  data: TimeScore;
}

// ---------------------------------------------------------------------------
// Healing scale: 1-10 (intuitive), derived from the 0-1 raw score
// ---------------------------------------------------------------------------

function toHealingScore(raw: number): number {
  return Math.max(1, Math.min(10, Math.round(raw * 10)));
}

// ---------------------------------------------------------------------------
// Status labels — clinically meaningful per healing level
// ---------------------------------------------------------------------------

function healingStatus(score: number): string {
  if (score >= 0.8) return "Healing well";
  if (score >= 0.6) return "Progressing";
  if (score >= 0.4) return "Needs attention";
  if (score >= 0.2) return "Concerning";
  return "Critical";
}

function statusColor(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-orange-400";
  return "text-rose-400";
}

function barColor(score: number): string {
  if (score >= 0.7) return "bg-emerald-400";
  if (score >= 0.4) return "bg-orange-400";
  return "bg-rose-400";
}

function statusBadge(score: number): string {
  if (score >= 0.7) return "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/15";
  if (score >= 0.4) return "bg-orange-500/10 text-orange-400 ring-1 ring-orange-500/15";
  return "bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/15";
}

// ---------------------------------------------------------------------------
// Dimension config — what each TIME dimension measures
// ---------------------------------------------------------------------------

const DIMENSION_CONFIG: Record<
  string,
  {
    label: string;
    measures: string;
    icon: React.ElementType;
    accent: string;
    iconColor: string;
  }
> = {
  tissue: {
    label: "Tissue",
    measures: "Wound bed tissue type",
    icon: Activity,
    accent: "bg-teal-400",
    iconColor: "text-teal-500",
  },
  inflammation: {
    label: "Inflammation",
    measures: "Infection & inflammation signs",
    icon: Flame,
    accent: "bg-orange-400",
    iconColor: "text-orange-500",
  },
  moisture: {
    label: "Moisture",
    measures: "Wound moisture balance",
    icon: Droplets,
    accent: "bg-sky-400",
    iconColor: "text-sky-500",
  },
  edge: {
    label: "Edge",
    measures: "Wound edge progression",
    icon: GitBranch,
    accent: "bg-violet-400",
    iconColor: "text-violet-500",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TimeScoreCard({ dimension, data }: TimeScoreCardProps) {
  const config = DIMENSION_CONFIG[dimension] || {
    label: dimension,
    measures: "",
    icon: Activity,
    accent: "bg-slate-400",
    iconColor: "text-muted-foreground",
  };

  const Icon = config.icon;
  const healing = toHealingScore(data.score);
  const status = healingStatus(data.score);
  const percent = Math.round(data.score * 100);

  return (
    <div className="apple-card overflow-hidden flex">
      {/* Left accent bar */}
      <div className={cn("w-1 shrink-0 rounded-l-xl", config.accent)} />

      <div className="flex-1 p-3 min-w-0">
        {/* Header: icon + label */}
        <div className="flex items-center gap-1.5 mb-2">
          <Icon className={cn("h-3.5 w-3.5 shrink-0", config.iconColor)} />
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider truncate">
            {config.label}
          </span>
        </div>

        {/* Clinical finding — the main content */}
        <p className="text-[13px] text-foreground font-medium leading-snug mb-1.5 first-letter:uppercase line-clamp-2">
          {data.type.toLowerCase()}
        </p>

        {/* Status badge */}
        <div className="flex items-center justify-between mb-2">
          <span
            className={cn(
              "text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap",
              statusBadge(data.score),
            )}
          >
            {status}
          </span>
          <span className={cn("text-sm font-bold tabular-nums", statusColor(data.score))}>
            {healing}<span className="text-[10px] font-normal text-muted-foreground/50">/10</span>
          </span>
        </div>

        {/* Healing bar with scale endpoints */}
        <div className="rounded-full h-1.5 w-full bg-muted">
          <div
            className={cn(
              "rounded-full h-1.5 transition-all duration-700 ease-out",
              barColor(data.score),
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[9px] text-muted-foreground/40">Critical</span>
          <span className="text-[9px] text-muted-foreground/40">Healed</span>
        </div>
      </div>
    </div>
  );
}
