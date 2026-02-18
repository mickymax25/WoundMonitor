"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  History,
  Volume2,
  FileText,
  ImageIcon,
  X,
  Eye,
} from "lucide-react";
import { listPatientAssessments } from "@/lib/api";
import { cn, formatDate, mediaUrl } from "@/lib/utils";
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
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [fullSizeImage, setFullSizeImage] = useState<string | null>(null);
  const [showPhotos, setShowPhotos] = useState(false);

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
    <>
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
              <div
                key={assessment.id}
                className={cn(
                  "w-full text-left rounded-xl p-3 transition-all",
                  "bg-[var(--surface-2)] ring-1",
                  isCurrent
                    ? "ring-primary/30 bg-primary/5"
                    : "ring-border/50",
                  "animate-slide-up"
                )}
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                {/* Clickable area: selects assessment + toggles expand */}
                <button
                  type="button"
                  onClick={() => {
                    onSelectAssessment(assessment);
                    setExpandedId(expandedId === assessment.id ? null : assessment.id);
                  }}
                  className="w-full text-left"
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

                {/* Expanded media section */}
                {expandedId === assessment.id && (
                  <div className="mt-2.5 pt-2.5 border-t border-border/30 space-y-2.5">
                    {/* Wound image thumbnails */}
                    {assessment.images && assessment.images.length > 0 ? (
                      <div className="flex gap-2 overflow-x-auto pb-1">
                        {assessment.images.map((img) => (
                          <button
                            key={img.id}
                            type="button"
                            onClick={() => {
                              if (!showPhotos) { setShowPhotos(true); return; }
                              setFullSizeImage(mediaUrl(img.image_path));
                            }}
                            className="shrink-0 overflow-hidden rounded-xl relative"
                          >
                            <img
                              src={mediaUrl(img.image_path)!}
                              alt={img.caption || "Wound"}
                              className={cn(
                                "w-16 h-16 object-cover ring-1",
                                img.is_primary ? "ring-primary/40" : "ring-border/30",
                                !showPhotos && "blur-lg scale-110"
                              )}
                            />
                            {!showPhotos && (
                              <div className="absolute inset-0 flex items-center justify-center">
                                <Eye className="h-3.5 w-3.5 text-white/50" />
                              </div>
                            )}
                          </button>
                        ))}
                      </div>
                    ) : assessment.image_path && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!showPhotos) { setShowPhotos(true); return; }
                          setFullSizeImage(mediaUrl(assessment.image_path));
                        }}
                        className="block overflow-hidden rounded-xl relative"
                      >
                        <img
                          src={mediaUrl(assessment.image_path)!}
                          alt="Wound"
                          className={cn(
                            "w-20 h-20 object-cover ring-1 ring-border/30",
                            !showPhotos && "blur-lg scale-110"
                          )}
                        />
                        {!showPhotos && (
                          <div className="absolute inset-0 flex items-center justify-center">
                            <Eye className="h-4 w-4 text-white/50" />
                          </div>
                        )}
                      </button>
                    )}

                    {/* Audio playback */}
                    {assessment.audio_path && (
                      <div className="flex items-center gap-2">
                        <Volume2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <audio
                          src={mediaUrl(assessment.audio_path)!}
                          controls
                          className="h-8 w-full max-w-[220px]"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    )}

                    {/* Text notes */}
                    {assessment.text_notes && (
                      <div className="flex items-start gap-2">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                        <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
                          {assessment.text_notes}
                        </p>
                      </div>
                    )}

                    {/* Show message when no media attached */}
                    {!assessment.audio_path && !assessment.text_notes && (
                      <p className="text-[10px] text-muted-foreground/40">
                        No audio or notes for this visit.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

    </div>

    {/* Full-size image modal — outside apple-card to avoid backdrop-filter breaking position:fixed */}
    {fullSizeImage && (
      <div
        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={() => setFullSizeImage(null)}
      >
        <button
          type="button"
          onClick={() => setFullSizeImage(null)}
          className="absolute top-4 right-4 w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center z-10"
        >
          <X className="h-5 w-5" />
        </button>
        <img
          src={fullSizeImage}
          alt="Wound full size"
          className="max-w-full max-h-full object-contain rounded-xl"
        />
      </div>
    )}
    </>
  );
}
