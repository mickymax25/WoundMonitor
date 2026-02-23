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
// BWAT per-item scale: 1 (best) to 5 (worst) — lower is better
// Thresholds aligned with total BWAT: <=2 ~ <=26/65, <=3.5 ~ <=45/65
// ---------------------------------------------------------------------------

function bwatColor(composite: number): string {
  if (composite <= 2.0) return "text-emerald-400";
  if (composite <= 3.0) return "text-sky-400";
  if (composite <= 4.0) return "text-orange-300";
  return "text-rose-400";
}

function bwatBarColor(composite: number): string {
  if (composite <= 2.0) return "bg-emerald-400";
  if (composite <= 3.0) return "bg-sky-400";
  if (composite <= 4.0) return "bg-orange-300";
  return "bg-rose-400";
}

function bwatAccentBorder(composite: number): string {
  if (composite <= 2.0) return "border-emerald-500/20";
  if (composite <= 3.0) return "border-sky-400/20";
  if (composite <= 4.0) return "border-orange-300/20";
  return "border-rose-500/20";
}

// Short BWAT item labels for compact display
const BWAT_SHORT: Record<string, string> = {
  necrotic_type: "Nec",
  necrotic_amount: "Amt",
  granulation: "Gran",
  skin_color: "Skin",
  edema: "Edm",
  induration: "Ind",
  exudate_type: "Exu",
  exudate_amount: "Amt",
  edges: "Edg",
  undermining: "Und",
  epithelialization: "Epi",
};

// ---------------------------------------------------------------------------
// Dimension config
// ---------------------------------------------------------------------------

const DIMENSION_CONFIG: Record<
  string,
  {
    label: string;
    icon: React.ElementType;
    iconColor: string;
  }
> = {
  tissue: {
    label: "Tissue",
    icon: Activity,
    iconColor: "text-teal-500",
  },
  inflammation: {
    label: "Inflammation",
    icon: Flame,
    iconColor: "text-orange-300",
  },
  moisture: {
    label: "Moisture",
    icon: Droplets,
    iconColor: "text-sky-500",
  },
  edge: {
    label: "Edge",
    icon: GitBranch,
    iconColor: "text-violet-500",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TimeScoreCard({ dimension, data }: TimeScoreCardProps) {
  const config = DIMENSION_CONFIG[dimension] || {
    label: dimension,
    icon: Activity,
    iconColor: "text-muted-foreground",
  };

  const Icon = config.icon;
  const hasBwat = data.bwat_composite != null && data.bwat_composite > 0;
  const composite = hasBwat ? data.bwat_composite! : null;

  // BWAT bar: 1=0%, 5=100% (higher = worse)
  const barPercent = composite != null ? Math.round(((composite - 1) / 4) * 100) : 0;

  return (
    <div
      className={cn(
        "apple-card overflow-hidden p-3",
        composite != null && bwatAccentBorder(composite),
      )}
    >
      {/* Row 1: icon + label + score */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <Icon className={cn("h-3.5 w-3.5 shrink-0", config.iconColor)} />
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            {config.label}
          </span>
        </div>
        {composite != null ? (
          <span className={cn("text-sm font-bold tabular-nums leading-none", bwatColor(composite))}>
            {composite.toFixed(1)}
            <span className="text-[9px] font-normal text-muted-foreground/40">/5</span>
          </span>
        ) : (
          <span className="text-[10px] text-muted-foreground/40">N/A</span>
        )}
      </div>

      {/* Row 2: clinical finding */}
      <p className="text-[11.5px] text-foreground/80 leading-snug mb-1.5 first-letter:uppercase line-clamp-2">
        {data.type.toLowerCase()}
      </p>

      {/* Row 3: bar */}
      {composite != null ? (
        <div className="rounded-full h-1 w-full bg-muted/60">
          <div
            className={cn(
              "rounded-full h-1 transition-all duration-700 ease-out",
              bwatBarColor(composite),
            )}
            style={{ width: `${barPercent}%` }}
          />
        </div>
      ) : (
        <div className="rounded-full h-1 w-full bg-muted/40" />
      )}

      {/* Row 4: compact BWAT items */}
      {hasBwat && data.bwat_items && Object.keys(data.bwat_items).length > 0 && (
        <div className="flex items-center gap-0.5 mt-1.5 overflow-hidden flex-wrap">
          {Object.entries(data.bwat_items).map(([key, val]) => (
            <span
              key={key}
              className={cn(
                "text-[8px] tabular-nums px-1 py-px rounded bg-muted/40",
                (val as number) <= 2
                  ? "text-emerald-400/70"
                  : (val as number) <= 3
                    ? "text-muted-foreground/50"
                    : "text-rose-400/70",
              )}
              title={key}
            >
              {BWAT_SHORT[key] || key.slice(0, 3)}:{val as number}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
