"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  History,
} from "lucide-react";
import { listPatientAssessments } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import type { AssessmentResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AssessmentHistoryProps {
  patientId: string;
  currentAssessmentId?: string;
  onSelectAssessment: (assessment: AssessmentResponse) => void;
  refreshKey: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TRAJECTORY_DISPLAY: Record<
  string,
  { icon: React.ReactNode; label: string; cls: string }
> = {
  improving: {
    icon: <TrendingUp className="h-3 w-3" />,
    label: "Improving",
    cls: "text-emerald-400 bg-emerald-500/10 ring-1 ring-emerald-500/15",
  },
  stable: {
    icon: <Minus className="h-3 w-3" />,
    label: "Stable",
    cls: "text-sky-400 bg-sky-500/10 ring-1 ring-sky-500/15",
  },
  deteriorating: {
    icon: <TrendingDown className="h-3 w-3" />,
    label: "Worsening",
    cls: "text-rose-400 bg-rose-500/10 ring-1 ring-rose-500/15",
  },
  baseline: {
    icon: <Minus className="h-3 w-3" />,
    label: "Baseline",
    cls: "text-slate-400 bg-slate-500/10 ring-1 ring-slate-500/15",
  },
};

const ALERT_DOT: Record<string, string> = {
  green: "bg-emerald-500",
  yellow: "bg-orange-300",
  orange: "bg-orange-300",
  red: "bg-rose-500",
};

function healingScore(assessment: AssessmentResponse): number {
  const tc = assessment.time_classification;
  if (!tc) return 0;
  const scores = (
    ["tissue", "inflammation", "moisture", "edge"] as const
  )
    .map((d) => tc[d]?.score)
    .filter((s): s is number => s != null && s > 0);
  if (scores.length === 0) return 0;
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  return Math.max(1, Math.min(10, Math.round(avg * 10)));
}

function barColor(score: number): string {
  if (score >= 7) return "bg-emerald-500";
  if (score >= 4) return "bg-orange-300";
  return "bg-rose-500";
}

function scoreTextColor(score: number): string {
  if (score >= 7) return "text-emerald-400";
  if (score >= 4) return "text-orange-300";
  return "text-rose-400";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AssessmentHistory({
  patientId,
  currentAssessmentId,
  onSelectAssessment,
  refreshKey,
}: AssessmentHistoryProps) {
  const [assessments, setAssessments] = useState<AssessmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAssessments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const all = await listPatientAssessments(patientId);
      const analyzed = all
        .filter((a) => a.time_classification !== null)
        .sort(
          (a, b) =>
            new Date(b.visit_date).getTime() - new Date(a.visit_date).getTime()
        );
      setAssessments(analyzed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history.");
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments, refreshKey]);

  // --- Loading skeleton ---
  if (loading) {
    return (
      <div className="apple-card p-4 space-y-3">
        <div className="flex items-center gap-2">
          <div className="skeleton w-5 h-5 rounded-md" />
          <div className="skeleton h-4 w-40 rounded-lg" />
        </div>
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="skeleton h-16 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="apple-card p-4">
        <p className="text-[13px] text-rose-400">{error}</p>
      </div>
    );
  }

  // --- Empty state ---
  if (assessments.length === 0) {
    return (
      <div className="apple-card p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-5 h-5 rounded-md bg-muted flex items-center justify-center ring-1 ring-border">
            <History className="h-2.5 w-2.5 text-muted-foreground" />
          </div>
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
            Visit History
          </h3>
        </div>
        <p className="text-[12px] text-muted-foreground/60 leading-relaxed">
          No assessments yet. Analyze a wound photo to start tracking.
        </p>
      </div>
    );
  }

  return (
    <div className="apple-card overflow-hidden">
      {/* Header / Toggle */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3.5 active:bg-[var(--surface-2)] transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center ring-1 ring-primary/15">
            <History className="h-2.5 w-2.5 text-primary" />
          </div>
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
            Visit History
          </h3>
          <span className="text-[11px] font-bold text-primary tabular-nums">
            {assessments.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground/40">
            1 (critical) → 10 (healed)
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground/50" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground/50" />
          )}
        </div>
      </button>

      {/* Collapsible list */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {assessments.map((assessment, idx) => {
            const isCurrent = assessment.id === currentAssessmentId;
            const traj =
              TRAJECTORY_DISPLAY[assessment.trajectory ?? "baseline"];
            const alertDot =
              ALERT_DOT[assessment.alert_level ?? ""] ?? "bg-slate-500";
            const hs = healingScore(assessment);
            const pct = hs * 10;

            return (
              <button
                key={assessment.id}
                type="button"
                onClick={() => onSelectAssessment(assessment)}
                className={cn(
                  "w-full text-left rounded-xl p-3 transition-all",
                  "bg-[var(--surface-2)] ring-1",
                  isCurrent
                    ? "ring-primary/30 bg-primary/5"
                    : "ring-border/50 active:ring-primary/20 active:bg-primary/5",
                  "animate-slide-up"
                )}
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                {/* Row 1: date + trajectory */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn("w-2 h-2 rounded-full shrink-0", alertDot)}
                    />
                    <span className="text-[13px] font-semibold text-foreground leading-tight">
                      {formatDate(assessment.visit_date)}
                    </span>
                    {isCurrent && (
                      <span className="text-[9px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
                        Current
                      </span>
                    )}
                  </div>
                  {traj && (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full",
                        traj.cls
                      )}
                    >
                      {traj.icon}
                      {traj.label}
                    </span>
                  )}
                </div>

                {/* Row 2: healing score bar */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 rounded-full h-2 bg-muted/50">
                    <div
                      className={cn(
                        "rounded-full h-2 transition-all duration-500",
                        barColor(hs)
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span
                    className={cn(
                      "text-sm font-bold tabular-nums w-8 text-right",
                      scoreTextColor(hs)
                    )}
                  >
                    {hs}
                    <span className="text-[9px] font-normal text-muted-foreground/40">
                      /10
                    </span>
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
