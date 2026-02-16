"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Clock,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  FileText,
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
  yellow: "bg-orange-400",
  orange: "bg-orange-500",
  red: "bg-rose-500",
};

/** Map a 0-3 TIME score to a color class for the mini bar. */
function scoreColor(score: number): string {
  if (score <= 1) return "bg-emerald-500";
  if (score === 2) return "bg-orange-400";
  return "bg-rose-500";
}

/** Shorten dimension label for compact display. */
const DIMENSION_LABELS: Record<string, string> = {
  tissue: "T",
  inflammation: "I",
  moisture: "M",
  edge: "E",
};

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
  const [expanded, setExpanded] = useState(false);
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

  // Only show past assessments (exclude the current one).
  const pastAssessments = assessments.filter(
    (a) => a.id !== currentAssessmentId
  );

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

  // --- Empty state: no other assessments exist ---
  if (pastAssessments.length === 0) {
    return (
      <div className="apple-card p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-5 h-5 rounded-md bg-muted flex items-center justify-center ring-1 ring-border">
            <History className="h-2.5 w-2.5 text-muted-foreground" />
          </div>
          <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
            Previous Assessments
          </h3>
        </div>
        <p className="text-[12px] text-muted-foreground/60 leading-relaxed">
          No previous assessments for this patient. Additional visits will
          appear here.
        </p>
      </div>
    );
  }

  // --- Show collapsed header with count, expand on click ---
  const visibleCount = expanded ? pastAssessments.length : 0;

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
            Previous Assessments
          </h3>
          <span className="text-[11px] font-bold text-primary tabular-nums">
            {pastAssessments.length}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground/50" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground/50" />
        )}
      </button>

      {/* Collapsible list */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {pastAssessments.map((assessment, idx) => {
            const isCurrent = assessment.id === currentAssessmentId;
            const traj =
              TRAJECTORY_DISPLAY[assessment.trajectory ?? "baseline"];
            const alertDot =
              ALERT_DOT[assessment.alert_level ?? ""] ?? "bg-slate-500";
            const tc = assessment.time_classification;

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
                <div className="flex items-start justify-between gap-2">
                  {/* Left: date + trajectory */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full shrink-0",
                          alertDot
                        )}
                      />
                      <span className="text-[13px] font-semibold text-foreground leading-tight">
                        {formatDate(assessment.visit_date)}
                      </span>
                    </div>

                    {/* Trajectory badge */}
                    {traj && (
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full mt-1.5",
                          traj.cls
                        )}
                      >
                        {traj.icon}
                        {traj.label}
                      </span>
                    )}
                  </div>

                  {/* Right: TIME mini-scores */}
                  {tc && (
                    <div className="flex items-center gap-1 shrink-0 pt-0.5">
                      {(
                        ["tissue", "inflammation", "moisture", "edge"] as const
                      ).map((dim) => {
                        const score = tc[dim].score;
                        return (
                          <div
                            key={dim}
                            className="flex flex-col items-center gap-0.5"
                          >
                            <span className="text-[8px] font-bold text-muted-foreground/50 uppercase">
                              {DIMENSION_LABELS[dim]}
                            </span>
                            <div
                              className={cn(
                                "w-5 h-1.5 rounded-full",
                                scoreColor(score)
                              )}
                              title={`${dim}: ${score}/3`}
                            />
                            <span className="text-[9px] font-bold text-muted-foreground/70 tabular-nums">
                              {score}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Report preview (first line) */}
                {assessment.report_text && (
                  <p className="text-[11px] text-muted-foreground/50 truncate mt-2 leading-tight">
                    <FileText className="inline h-3 w-3 mr-1 -mt-0.5" />
                    {assessment.report_text.slice(0, 100)}
                    {assessment.report_text.length > 100 ? "..." : ""}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
