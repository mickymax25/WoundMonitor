"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Camera,
  X,
  Eye,
  EyeOff,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { listPatientAssessments } from "@/lib/api";
import { cn, formatDate, formatDateShort, mediaUrl } from "@/lib/utils";
import type { AssessmentResponse } from "@/lib/types";

interface PhotoTimelineProps {
  patientId: string;
  refreshKey: number;
  onSelectAssessment?: (assessment: AssessmentResponse) => void;
}

const TRAJ_DOT: Record<string, string> = {
  improving: "bg-emerald-500",
  stable: "bg-sky-400",
  deteriorating: "bg-rose-500",
  baseline: "bg-slate-400",
};

const TRAJ_CONFIG: Record<
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

function getBwatTotal(a: AssessmentResponse): number | null {
  if (a.bwat_total && a.bwat_total > 0) return a.bwat_total;
  return null;
}

function bwatScoreColor(total: number): string {
  if (total <= 26) return "text-emerald-400";
  if (total <= 39) return "text-sky-400";
  if (total <= 52) return "text-orange-300";
  return "text-rose-400";
}

function bwatBarColor(total: number): string {
  if (total <= 26) return "bg-emerald-400";
  if (total <= 39) return "bg-sky-400";
  if (total <= 52) return "bg-orange-300";
  return "bg-rose-500";
}

function reportExcerpt(text: string | null): string {
  if (!text) return "";
  // Strip markdown and skip metadata header lines
  const lines = text.split("\n").filter((l) => {
    const trimmed = l.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith("#")) return false;
    if (/^\*\*\w[^*]*:\*\*/.test(trimmed)) return false;
    if (/^[-–—]\s*\*\*/.test(trimmed)) return false;
    return true;
  });
  // Join remaining lines, strip markdown bold/italic
  const clean = lines
    .join(" ")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (!clean) return "";
  // Take first 2 sentences
  const sentences = clean.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ");
  if (sentences.length <= 160) return sentences;
  return sentences.slice(0, 157) + "...";
}

// ---------------------------------------------------------------------------
// Gallery Modal
// ---------------------------------------------------------------------------

function GalleryModal({
  assessments,
  initialIndex,
  onClose,
}: {
  assessments: AssessmentResponse[];
  initialIndex: number;
  onClose: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(initialIndex);

  // Scroll to initial slide on mount
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const slideWidth = el.offsetWidth;
    el.scrollTo({ left: slideWidth * initialIndex, behavior: "instant" as ScrollBehavior });
  }, [initialIndex]);

  // Track active slide via scroll position (debounced to avoid jank)
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleScroll = useCallback(() => {
    if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current);
    scrollTimerRef.current = setTimeout(() => {
      const el = scrollRef.current;
      if (!el) return;
      const slideWidth = el.offsetWidth;
      if (slideWidth === 0) return;
      const idx = Math.round(el.scrollLeft / slideWidth);
      setActiveIndex(Math.max(0, Math.min(assessments.length - 1, idx)));
    }, 80);
  }, [assessments.length]);

  const goTo = useCallback(
    (idx: number) => {
      const el = scrollRef.current;
      if (!el) return;
      const clamped = Math.max(0, Math.min(assessments.length - 1, idx));
      el.scrollTo({ left: el.offsetWidth * clamped, behavior: "smooth" });
      setActiveIndex(clamped);
    },
    [assessments.length]
  );

  const current = assessments[activeIndex];

  return (
    <div className="fixed inset-0 z-50 flex flex-col backdrop-blur-xl wc-hero" style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}>
      {/* Photo area with overlaid header */}
      <div className="relative flex-1 min-h-0">
        {/* Overlay header — sits on top of photo area */}
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 pt-2 pb-6"
             style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.45) 0%, transparent 100%)" }}>
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-white/90">
              {formatDate(current?.visit_date ?? "")}
            </span>
            <span className="text-[11px] text-white/40 tabular-nums">
              {activeIndex + 1} / {assessments.length}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-10 h-10 rounded-full bg-black/30 text-white flex items-center justify-center active:bg-black/50 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full flex overflow-x-auto snap-x snap-mandatory scrollbar-hide"
          style={{ overscrollBehaviorX: "contain", WebkitOverflowScrolling: "touch" }}
        >
          {assessments.map((a) => {
            const imgUrl = mediaUrl(a.image_path);
            return (
              <div
                key={a.id}
                className="w-full h-full shrink-0 snap-center flex items-center justify-center px-4 py-2"
                onClick={onClose}
              >
                <img
                  src={imgUrl!}
                  alt="Wound"
                  className="max-w-full max-h-full object-contain rounded-2xl"
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            );
          })}
        </div>

        {/* Arrow buttons */}
        {activeIndex > 0 && (
          <button
            type="button"
            onClick={() => goTo(activeIndex - 1)}
            className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full
                       bg-black/40 text-white/70 flex items-center justify-center
                       active:bg-black/60 transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        )}
        {activeIndex < assessments.length - 1 && (
          <button
            type="button"
            onClick={() => goTo(activeIndex + 1)}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full
                       bg-black/40 text-white/70 flex items-center justify-center
                       active:bg-black/60 transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Info panel — fixed height to prevent layout shift on swipe */}
      <div className="shrink-0 px-5 pb-5 pt-3 min-h-[150px]">
        {current && (
          <div className="space-y-2.5">
            {/* Row 1: Trajectory + Score cartouche | TIME cartouche */}
            <div className="flex items-center gap-2">
              {/* Trajectory + Healing score — unified cartouche */}
              <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/[0.06] ring-1 ring-white/10 flex-1 min-w-0">
                {current.trajectory && TRAJ_CONFIG[current.trajectory] && (
                  <div className={cn(
                    "flex items-center gap-1 text-[11px] font-semibold shrink-0",
                    TRAJ_CONFIG[current.trajectory].cls.replace(/bg-\S+/g, "").replace(/ring-\S+/g, "")
                  )}>
                    {TRAJ_CONFIG[current.trajectory].icon}
                    <span>{TRAJ_CONFIG[current.trajectory].label}</span>
                  </div>
                )}
                {(() => {
                  const bt = getBwatTotal(current);
                  if (bt == null) return null;
                  const pct = Math.round(((65 - bt) / 52) * 100);
                  return (
                    <>
                      <span className="w-px h-4 bg-white/10 shrink-0" />
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div className="flex-1 rounded-full h-1.5 bg-white/10">
                          <div
                            className={cn("rounded-full h-1.5", bwatBarColor(bt))}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className={cn("text-[13px] font-bold tabular-nums shrink-0", bwatScoreColor(bt))}>
                          {bt}
                          <span className="text-[9px] font-normal text-white/30">/65</span>
                        </span>
                      </div>
                    </>
                  );
                })()}
              </div>

              {/* BWAT dimension cartouche */}
              {current.time_classification && (
                <div className="shrink-0 flex items-center gap-2 px-2.5 py-2 rounded-xl bg-white/[0.06] ring-1 ring-white/10">
                  {(["tissue", "inflammation", "moisture", "edge"] as const).map((dim, i) => {
                    const s = current.time_classification![dim];
                    if (!s) return null;
                    const comp = s.bwat_composite;
                    if (comp == null || comp <= 0) return null;
                    return (
                      <React.Fragment key={dim}>
                        {i > 0 && <span className="w-px h-4 bg-white/10" />}
                        <div className="flex flex-col items-center min-w-[16px]">
                          <span className="text-[8px] font-bold text-white/40 uppercase leading-none tracking-wider">
                            {dim.charAt(0)}
                          </span>
                          <span className={cn(
                            "text-[12px] font-bold tabular-nums leading-tight",
                            comp <= 2.0 ? "text-emerald-400" : comp <= 3.5 ? "text-orange-300" : "text-rose-400"
                          )}>
                            {comp.toFixed(1)}
                          </span>
                        </div>
                      </React.Fragment>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Report excerpt — fixed 3 lines */}
            <p className="text-[12px] text-white/50 leading-relaxed line-clamp-3 min-h-[3.6em]">
              {current.report_text ? reportExcerpt(current.report_text) : "No report available."}
            </p>

            {/* Navigation dots */}
            {assessments.length > 1 && (
              <div className="flex items-center justify-center gap-1.5">
                {assessments.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => goTo(idx)}
                    className={cn(
                      "rounded-full transition-all",
                      idx === activeIndex
                        ? "w-5 h-2 bg-primary"
                        : "w-2 h-2 bg-white/20 active:bg-white/40"
                    )}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function PhotoTimeline({
  patientId,
  refreshKey,
  onSelectAssessment,
}: PhotoTimelineProps) {
  const [assessments, setAssessments] = useState<AssessmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPhotos, setShowPhotos] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const all = await listPatientAssessments(patientId);
      const withImages = all
        .filter((a) => a.image_path)
        .sort(
          (a, b) =>
            new Date(a.visit_date).getTime() - new Date(b.visit_date).getTime()
        );
      setAssessments(withImages);
    } catch {
      // Silent fail — not critical
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
        <div className="flex items-center gap-2 mb-3">
          <div className="skeleton w-5 h-5 rounded-md" />
          <div className="skeleton h-3 w-32 rounded-lg" />
        </div>
        <div className="flex gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton w-[72px] h-[72px] rounded-xl shrink-0" />
          ))}
        </div>
      </div>
    );
  }

  if (assessments.length === 0) return null;

  return (
    <>
      <div className="apple-card overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center ring-1 ring-primary/15">
              <Camera className="h-2.5 w-2.5 text-primary" />
            </div>
            <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
              Photo Timeline
            </h3>
            <span className="text-[11px] font-bold text-primary tabular-nums">
              {assessments.length}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowPhotos((v) => !v)}
            className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground/60 active:text-muted-foreground transition-colors px-2 py-1 -mr-2"
          >
            {showPhotos ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            {showPhotos ? "Hide" : "Show"}
          </button>
        </div>

        {/* Horizontal scrollable strip */}
        <div className="overflow-x-auto px-4 pb-4 pt-1 scrollbar-hide">
          <div className="flex gap-3">
            {assessments.map((assessment, idx) => {
              const imgUrl = mediaUrl(assessment.image_path);
              const trajDot = TRAJ_DOT[assessment.trajectory ?? "baseline"];

              return (
                <button
                  key={assessment.id}
                  type="button"
                  onClick={() => {
                    if (!showPhotos) {
                      setShowPhotos(true);
                      return;
                    }
                    setGalleryIndex(idx);
                  }}
                  className="shrink-0 flex flex-col items-center gap-1.5 group"
                >
                  <div className="relative overflow-hidden rounded-xl">
                    <img
                      src={imgUrl!}
                      alt="Wound"
                      className={cn(
                        "w-[72px] h-[72px] object-cover ring-1 ring-border/30 group-active:ring-primary/40 transition-all",
                        !showPhotos && "blur-lg scale-110"
                      )}
                    />
                    {!showPhotos && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Eye className="h-4 w-4 text-white/50" />
                      </div>
                    )}
                    {trajDot && (
                      <span
                        className={cn(
                          "absolute bottom-1 right-1 w-2.5 h-2.5 rounded-full ring-2 ring-[var(--surface-1)]",
                          trajDot
                        )}
                      />
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground/60 font-medium">
                    {formatDateShort(assessment.visit_date)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Gallery modal — rendered outside apple-card to avoid backdrop-filter breaking position:fixed */}
      {galleryIndex !== null && (
        <GalleryModal
          assessments={assessments}
          initialIndex={galleryIndex}
          onClose={() => setGalleryIndex(null)}
        />
      )}
    </>
  );
}
