"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn, scoreToPercent } from "@/lib/utils";
import type { TimeScore } from "@/lib/types";

interface TimeScoreCardProps {
  dimension: string;
  data: TimeScore;
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.4) return "bg-amber-500";
  return "bg-rose-500";
}

function scoreBorderColor(score: number): string {
  if (score >= 0.7) return "border-emerald-500/30";
  if (score >= 0.4) return "border-amber-500/30";
  return "border-rose-500/30";
}

function scoreTextColor(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-amber-400";
  return "text-rose-400";
}

const DIMENSION_LABELS: Record<string, string> = {
  tissue: "Tissue",
  inflammation: "Inflammation",
  moisture: "Moisture",
  edge: "Edge",
};

export function TimeScoreCard({ dimension, data }: TimeScoreCardProps) {
  const percent = scoreToPercent(data.score);
  const label = DIMENSION_LABELS[dimension] || dimension;

  return (
    <Card
      className={cn(
        "border transition-colors",
        scoreBorderColor(data.score)
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-foreground">
            {label}
          </span>
          <span
            className={cn(
              "text-lg font-mono font-bold",
              scoreTextColor(data.score)
            )}
          >
            {percent}%
          </span>
        </div>
        <p className="text-xs text-muted-foreground mb-3 capitalize">
          {data.type}
        </p>
        <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              scoreColor(data.score)
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
