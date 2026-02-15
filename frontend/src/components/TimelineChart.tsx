"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  Activity,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTrajectory } from "@/lib/api";
import { cn, formatDateShort } from "@/lib/utils";
import type { TrajectoryPoint } from "@/lib/types";

interface TimelineChartProps {
  patientId: string;
  refreshKey: number;
}

const SERIES = [
  { key: "tissue_score", name: "Tissue", color: "#059669" },
  { key: "inflammation_score", name: "Inflammation", color: "#d97706" },
  { key: "moisture_score", name: "Moisture", color: "#0891b2" },
  { key: "edge_score", name: "Edge", color: "#7c3aed" },
] as const;

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
  }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-card border border-border rounded-xl p-3 shadow-lg">
      <p className="text-xs text-muted-foreground mb-2 font-medium">{label}</p>
      <div className="space-y-1.5">
        {payload.map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between gap-6 text-xs"
          >
            <span className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-foreground/70">{entry.name}</span>
            </span>
            <span className="font-mono font-semibold text-foreground">
              {(entry.value * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
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

function trajectoryBorderColor(trajectory: string | null): string {
  switch (trajectory) {
    case "improving":
      return "border-emerald-500/30";
    case "deteriorating":
      return "border-rose-500/30";
    case "stable":
      return "border-sky-500/30";
    default:
      return "border-border";
  }
}

export function TimelineChart({
  patientId,
  refreshKey,
}: TimelineChartProps) {
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
      setError(
        err instanceof Error ? err.message : "Failed to load trajectory."
      );
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshKey]);

  const chartData = data.map((point) => ({
    ...point,
    date: formatDateShort(point.visit_date),
  }));

  return (
    <Card className="h-full flex flex-col border-border shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2 font-semibold">
          <Activity className="h-4 w-4 text-primary" />
          Wound Trajectory
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center border border-border">
              <Loader2 className="h-6 w-6 animate-spin text-primary/60" />
            </div>
            <p className="text-xs text-muted-foreground">Loading trajectory...</p>
          </div>
        ) : error ? (
          <p className="text-sm text-rose-400 text-center py-8">
            {error}
          </p>
        ) : data.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
            <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center mb-3 border border-border">
              <Activity className="h-7 w-7 opacity-40" />
            </div>
            <p className="text-sm font-medium">No assessment data yet</p>
            <p className="text-xs mt-1 text-muted-foreground/60">
              Analyze a wound photo to begin tracking.
            </p>
          </div>
        ) : (
          <>
            {/* Legend */}
            <div className="flex flex-wrap gap-3 mb-4">
              {SERIES.map((s) => (
                <div key={s.key} className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: s.color }}
                  />
                  <span className="text-xs text-muted-foreground font-medium">
                    {s.name}
                  </span>
                </div>
              ))}
            </div>

            {/* Area Chart */}
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 5, right: 10, left: -15, bottom: 5 }}
                >
                  <defs>
                    {SERIES.map((s) => (
                      <linearGradient
                        key={s.key}
                        id={`gradient-${s.key}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={s.color}
                          stopOpacity={0.2}
                        />
                        <stop
                          offset="100%"
                          stopColor={s.color}
                          stopOpacity={0.02}
                        />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="hsl(228 28% 22%)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "hsl(215 15% 55%)" }}
                    stroke="hsl(228 28% 22%)"
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: "hsl(215 15% 55%)" }}
                    stroke="hsl(228 28% 22%)"
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{
                      stroke: "hsl(228 28% 28%)",
                      strokeDasharray: "4 4",
                    }}
                  />
                  {SERIES.map((s) => (
                    <Area
                      key={s.key}
                      type="monotone"
                      dataKey={s.key}
                      name={s.name}
                      stroke={s.color}
                      strokeWidth={2}
                      fill={`url(#gradient-${s.key})`}
                      dot={{
                        r: 4,
                        fill: s.color,
                        stroke: "hsl(230 35% 12%)",
                        strokeWidth: 2,
                      }}
                      activeDot={{
                        r: 6,
                        fill: s.color,
                        stroke: "hsl(230 35% 12%)",
                        strokeWidth: 2,
                      }}
                      connectNulls
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Visit History thumbnails */}
            <div className="mt-5 pt-4 border-t border-border">
              <p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wider">
                Visit History
              </p>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {data.map((point, idx) => (
                  <div
                    key={idx}
                    className="shrink-0 text-center"
                  >
                    <div
                      className={cn(
                        "w-14 h-14 rounded-lg bg-[var(--surface-2)] border flex flex-col items-center justify-center gap-0.5 transition-colors",
                        trajectoryBorderColor(point.trajectory)
                      )}
                    >
                      <span className="text-xs font-bold text-foreground/80">
                        #{idx + 1}
                      </span>
                      {trajectoryIcon(point.trajectory)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 font-medium">
                      {formatDateShort(point.visit_date)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
