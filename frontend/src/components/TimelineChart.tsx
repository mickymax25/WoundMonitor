"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Activity, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTrajectory } from "@/lib/api";
import { formatDateShort } from "@/lib/utils";
import type { TrajectoryPoint } from "@/lib/types";

interface TimelineChartProps {
  patientId: string;
  refreshKey: number;
}

const SERIES = [
  { key: "tissue_score", name: "Tissue", color: "#10b981" },
  { key: "inflammation_score", name: "Inflammation", color: "#f59e0b" },
  { key: "moisture_score", name: "Moisture", color: "#0ea5e9" },
  { key: "edge_score", name: "Edge", color: "#a855f7" },
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
    <div className="bg-slate-900 border border-border rounded-lg p-3 shadow-lg">
      <p className="text-xs text-muted-foreground mb-2">{label}</p>
      {payload.map((entry) => (
        <div
          key={entry.name}
          className="flex items-center justify-between gap-4 text-xs"
        >
          <span className="flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            {entry.name}
          </span>
          <span className="font-mono text-foreground">
            {(entry.value * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
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
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          Wound Trajectory
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <p className="text-sm text-red-400 text-center py-8">
            {error}
          </p>
        ) : data.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
            <Activity className="h-8 w-8 mb-2 opacity-40" />
            <p className="text-sm">No assessment data yet.</p>
            <p className="text-xs mt-1">
              Analyze a wound photo to begin tracking.
            </p>
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 5, right: 10, left: -10, bottom: 5 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(217 33% 22%)"
                />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "hsl(215 20% 65%)" }}
                  stroke="hsl(217 33% 22%)"
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fontSize: 11, fill: "hsl(215 20% 65%)" }}
                  stroke="hsl(217 33% 22%)"
                  tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 11 }}
                  iconSize={8}
                  iconType="circle"
                />
                {SERIES.map((s) => (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={s.color}
                    strokeWidth={2}
                    dot={{ r: 3, fill: s.color }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Trajectory labels below chart */}
        {data.length > 0 && (
          <div className="mt-4 pt-3 border-t border-border">
            <p className="text-xs text-muted-foreground mb-2 font-medium">
              Visit History
            </p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {data.map((point, idx) => (
                <div
                  key={idx}
                  className="shrink-0 text-center"
                >
                  <div className="w-12 h-12 rounded-md bg-slate-800 border border-border flex items-center justify-center text-xs text-muted-foreground">
                    #{idx + 1}
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {formatDateShort(point.visit_date)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
