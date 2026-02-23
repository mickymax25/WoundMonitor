"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  BarChart3,
} from "lucide-react";
import { getTrajectory } from "@/lib/api";
import { cn, formatDateShort } from "@/lib/utils";
import type { TrajectoryPoint } from "@/lib/types";

interface TimelineChartProps {
  patientId: string;
  refreshKey: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// BWAT severity helpers — lower score = better
function bwatBarColor(total: number): string {
  if (total <= 26) return "bg-emerald-400";
  if (total <= 39) return "bg-sky-400";
  if (total <= 52) return "bg-orange-300";
  return "bg-rose-500";
}

function bwatBarBg(total: number): string {
  if (total <= 26) return "bg-emerald-500/10";
  if (total <= 39) return "bg-sky-400/10";
  if (total <= 52) return "bg-orange-300/10";
  return "bg-rose-500/10";
}

function bwatTextColor(total: number): string {
  if (total <= 26) return "text-emerald-400";
  if (total <= 39) return "text-sky-400";
  if (total <= 52) return "text-orange-300";
  return "text-rose-400";
}

function trajectoryIcon(trajectory: string | null) {
  switch (trajectory) {
    case "improving":
      return <TrendingUp className="h-3 w-3 text-emerald-400" />;
    case "deteriorating":
      return <TrendingDown className="h-3 w-3 text-rose-400" />;
    case "stable":
      return <Minus className="h-3 w-3 text-sky-400" />;
    default:
      return null;
  }
}

function trajectoryLabel(trajectory: string | null): string {
  switch (trajectory) {
    case "improving": return "Improving";
    case "deteriorating": return "Worsening";
    case "stable": return "Stable";
    default: return "Baseline";
  }
}

function trajectoryTextColor(trajectory: string | null): string {
  switch (trajectory) {
    case "improving": return "text-emerald-400";
    case "deteriorating": return "text-rose-400";
    case "stable": return "text-sky-400";
    default: return "text-muted-foreground";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TimelineChart({ patientId, refreshKey }: TimelineChartProps) {
  const [data, setData] = useState<TrajectoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const points = await getTrajectory(patientId);
      setData(points);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load trajectory.");
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshKey]);

  if (loading) {
    return (
      <div className="apple-card p-4">
        <div className="flex items-center justify-center h-32 gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-primary/60" />
          <span className="text-xs text-muted-foreground">Loading trend...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="apple-card p-4">
        <p className="text-sm text-rose-400 text-center py-6">{error}</p>
      </div>
    );
  }

  if (data.length < 2) {
    return (
      <div className="apple-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Healing Trend</span>
        </div>
        <p className="text-xs text-muted-foreground text-center py-6">
          At least 2 visits needed to show the healing trend.
        </p>
      </div>
    );
  }

  return (
    <div className="apple-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Healing Trend</span>
        </div>
        <div className="flex items-center gap-1 text-[11px]">
          <span className="text-muted-foreground">BWAT:</span>
          <span className="text-emerald-400">13</span>
          <span className="text-muted-foreground/50">→</span>
          <span className="text-rose-400">65</span>
        </div>
      </div>

      {/* Visit bars */}
      <div className="space-y-2.5">
        {data.map((point, idx) => {
          const bt = point.bwat_total;
          if (bt == null || bt <= 0) return null;
          // Inverted: lower BWAT = more bar (better)
          const pct = Math.round(((65 - bt) / 52) * 100);

          return (
            <div key={idx} className={cn("rounded-lg p-2.5 border border-border/30", bwatBarBg(bt))}>
              {/* Row: date + trajectory + score */}
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    Visit {idx + 1}
                  </span>
                  <span className="text-[11px] text-muted-foreground/60">
                    {formatDateShort(point.visit_date)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  {trajectoryIcon(point.trajectory)}
                  <span className={cn("text-[11px] font-medium", trajectoryTextColor(point.trajectory))}>
                    {trajectoryLabel(point.trajectory)}
                  </span>
                </div>
              </div>

              {/* Bar */}
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-full h-2 bg-muted/50">
                  <div
                    className={cn("rounded-full h-2 transition-all duration-500", bwatBarColor(bt))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className={cn("text-sm font-bold tabular-nums w-10 text-right", bwatTextColor(bt))}>
                  {bt}
                  <span className="text-[9px] font-normal text-muted-foreground/40">/65</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
