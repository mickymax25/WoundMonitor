"use client";

import React, { useState, useMemo } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  FileText,
  Stethoscope,
  TrendingUp,
  TrendingDown,
  Minus,
  Circle,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  ShieldAlert,
  Bot,
  Send,
  MessageCircle,
} from "lucide-react";
import { TimeScoreCard } from "@/components/TimeScoreCard";
import { ReferralDialog } from "@/components/ReferralDialog";
import { cn, formatDate } from "@/lib/utils";
import type { AnalysisResult, TimeClassification } from "@/lib/types";

interface ReportPanelProps {
  result: AnalysisResult | null;
  patientId?: string | null;
  patientName?: string | null;
  woundType?: string | null;
  referringPhysician?: string | null;
  referringPhysicianPhone?: string | null;
  referringPhysicianEmail?: string | null;
  referringPhysicianPreferredContact?: string | null;
  renderBeforeSummary?: React.ReactNode;
}

function woundTypeLabel(type: string | null | undefined): string {
  if (!type) return "Unspecified";
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const TRAJECTORY_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; color: string; bg: string }
> = {
  improving: {
    label: "Improving",
    icon: <TrendingUp className="h-3.5 w-3.5" />,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
  },
  stable: {
    label: "Stable",
    icon: <Minus className="h-3.5 w-3.5" />,
    color: "text-sky-400",
    bg: "bg-sky-500/10",
  },
  deteriorating: {
    label: "Deteriorating",
    icon: <TrendingDown className="h-3.5 w-3.5" />,
    color: "text-rose-400",
    bg: "bg-rose-500/10",
  },
  baseline: {
    label: "Baseline",
    icon: <Circle className="h-3.5 w-3.5" />,
    color: "text-muted-foreground",
    bg: "bg-muted",
  },
};

function AlertCard({
  level,
  detail,
  secondaryDetail,
  referralSent,
  onReferralClick,
}: {
  level: string;
  detail: string | null;
  secondaryDetail?: string | null;
  referralSent: boolean;
  onReferralClick: () => void;
}) {
  if (level === "green") return null;

  const isRed = level === "red";
  const isOrangeOrRed = level === "orange" || level === "red";

  const config: Record<
    string,
    {
      icon: React.ReactNode;
      label: string;
      accentColor: string;
      textColor: string;
      iconBg: string;
      cardBorder: string;
      glowShadow: string;
      btnBg: string;
      btnText: string;
      btnRing: string;
    }
  > = {
    yellow: {
      icon: <Info className="h-4 w-4" />,
      label: "Advisory",
      accentColor: "bg-orange-300",
      textColor: "text-orange-300",
      iconBg: "bg-orange-300/15 ring-orange-300/20",
      cardBorder: "border-orange-300/15",
      glowShadow: "",
      btnBg: "bg-orange-300/10",
      btnText: "text-orange-300",
      btnRing: "ring-orange-300/20",
    },
    orange: {
      icon: <AlertCircle className="h-4 w-4" />,
      label: "Warning",
      accentColor: "bg-orange-300",
      textColor: "text-orange-300",
      iconBg: "bg-orange-300/15 ring-orange-300/20",
      cardBorder: "border-orange-300/15",
      glowShadow: "shadow-[0_0_20px_rgba(253,186,116,0.06)]",
      btnBg: "bg-orange-300/10",
      btnText: "text-orange-300",
      btnRing: "ring-orange-300/20",
    },
    red: {
      icon: <AlertTriangle className="h-4 w-4" />,
      label: "Critical Alert",
      accentColor: "bg-rose-500",
      textColor: "text-rose-300",
      iconBg: "bg-rose-500/15 ring-rose-500/20",
      cardBorder: "border-rose-500/20",
      glowShadow: "shadow-[0_0_24px_rgba(244,63,94,0.08)]",
      btnBg: "bg-rose-500/15",
      btnText: "text-rose-300",
      btnRing: "ring-rose-500/25",
    },
  };

  const c = config[level] || config.yellow;

  return (
    <div
      className={cn(
        "apple-card overflow-hidden border",
        c.cardBorder,
        c.glowShadow,
        isRed && "animate-alert-pulse"
      )}
      role="alert"
    >
      {/* Accent top bar */}
      <div className={cn("h-[3px]", c.accentColor)} />

      <div className="p-4">
        {/* Alert header */}
        <div className="flex items-start gap-3">
          <div className={cn("w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ring-1", c.iconBg, c.textColor)}>
            {c.icon}
          </div>
          <div className="flex-1 min-w-0">
            <p className={cn("text-[14px] font-bold leading-tight", c.textColor)}>
              {c.label}
            </p>
            {detail && (
              <p className="text-[12px] text-muted-foreground mt-1 leading-relaxed">
                {detail}
              </p>
            )}
            {secondaryDetail && (
              <p className="text-[12px] text-muted-foreground/80 mt-1.5 leading-relaxed">
                {secondaryDetail}
              </p>
            )}
          </div>
        </div>

        {/* Referral action — integrated inside the alert card */}
        {isOrangeOrRed && (
          <div className="mt-3 pt-3 border-t border-border/20">
            {referralSent ? (
              <div className="flex items-center gap-2 text-[12px] font-semibold text-emerald-400">
                <CheckCircle className="h-3.5 w-3.5" />
                Referral sent successfully
              </div>
            ) : (
              <button
                type="button"
                onClick={onReferralClick}
                className={cn(
                  "w-full flex items-center justify-center gap-2 h-10 rounded-xl",
                  "text-[12px] font-semibold transition-colors active:opacity-80 ring-1",
                  c.btnBg, c.btnText, c.btnRing
                )}
              >
                <Send className="h-3.5 w-3.5" />
                Refer to Physician
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CollapsibleSection({
  title,
  icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="apple-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left",
          "min-h-[48px] transition-colors"
        )}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-primary/60">{icon}</span>
          <span className="text-[13px] font-semibold text-foreground">
            {title}
          </span>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground/50 shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground/50 shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-0">
          <div className="border-t border-border pt-3">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

interface ParsedReport {
  observations: { label: string; text: string }[];
  recommendations: string[];
  clinicalGuidance: { question: string; answer: string }[];
  remainingText: string;
}

function parseReportText(reportText: string): ParsedReport {
  const lines = reportText.split("\n");
  const observations: { label: string; text: string }[] = [];
  const recommendations: string[] = [];
  const clinicalGuidance: { question: string; answer: string }[] = [];
  const remainingLines: string[] = [];

  let inRecommendations = false;
  let inGuidance = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    // Detect Clinical Guidance header
    if (/^#{1,4}\s+Clinical\s+Guidance/i.test(line)) {
      inGuidance = true;
      inRecommendations = false;
      continue;
    }

    // If in guidance section, parse Q&A bullets
    if (inGuidance) {
      // Exit guidance on next section header
      const isSectionHeader =
        /^#{1,4}\s+/.test(line) ||
        /^\d+\.\s+\*\*.+\*\*[:\s]*$/.test(line);
      if (isSectionHeader) {
        inGuidance = false;
        // fall through to normal parsing
      } else {
        // Parse "- Q: ... — A: ..." or "- Q: ... - A: ..."
        const qaMatch = line.match(/^[-*]\s+Q:\s*(.+?)\s*[—–-]+\s*A:\s*(.+)/i);
        if (qaMatch) {
          clinicalGuidance.push({
            question: cleanInline(qaMatch[1].replace(/\?$/, "").trim()),
            answer: cleanInline(qaMatch[2]),
          });
          continue;
        }
        // Skip subtitle like "*Answers to nurse questions...*"
        if (/^\*.*\*$/.test(line) || line === "") continue;
        // Generic bullet in guidance
        const bullet = line.match(/^[-*]\s+(.*)/);
        if (bullet) {
          clinicalGuidance.push({ question: "", answer: cleanInline(bullet[1]) });
          continue;
        }
        continue;
      }
    }

    const recHeaderPatterns = [
      /recommended\s+interventions/i,
      /recommendations/i,
      /treatment\s+plan/i,
      /next\s+steps/i,
      /action\s+items/i,
    ];
    const isRecHeader =
      recHeaderPatterns.some((p) => p.test(line)) &&
      (/^#{1,4}\s/.test(line) ||
        /^\d+\.\s+\*\*/.test(line) ||
        /^\*\*/.test(line));
    if (isRecHeader) {
      inRecommendations = true;
      continue;
    }

    const isSectionHeader =
      /^#{1,4}\s+/.test(line) ||
      /^\d+\.\s+\*\*.+\*\*[:\s]*$/.test(line);
    if (isSectionHeader && inRecommendations && !isRecHeader) {
      inRecommendations = false;
    }

    if (
      inRecommendations &&
      (/^\d+\.\s+\*\*follow/i.test(line) || /^\*\*note/i.test(line))
    ) {
      inRecommendations = false;
    }

    if (inRecommendations) {
      const bulletMatch = line.match(/^[-*]\s+(.*)/);
      const numberedMatch = line.match(/^\d+\.\s+(.*)/);
      const itemText = bulletMatch?.[1] || numberedMatch?.[1];
      if (itemText) {
        recommendations.push(cleanInline(itemText));
        continue;
      }
      if (line === "") continue;
      if (line.length > 0) {
        recommendations.push(cleanInline(line));
        continue;
      }
    }

    const skipLabels = new Set([
      "patient", "wound type", "wound location", "visit date",
      "tissue", "inflammation", "moisture", "edge",
      "trajectory", "cosine change score", "change score",
      "time classification", "clinical summary", "note",
      "follow-up timeline",
    ]);

    const boldLabelPatterns = [
      line.match(/^[-*]\s+\*\*(.+?)\*\*[:\s]*(.+)/),
      line.match(/^\d+\.\s+\*\*(.+?)\*\*[:\s]*(.+)/),
      line.match(/^\*\*(.+?)\*\*[:\s]+(.+)/),
    ];
    const boldMatch = boldLabelPatterns.find((m) => m !== null);
    if (boldMatch && !inRecommendations) {
      const label = boldMatch[1].replace(/:$/, "");
      if (!skipLabels.has(label.toLowerCase())) {
        observations.push({ label, text: cleanInline(boldMatch[2]) });
      }
      continue;
    }

    remainingLines.push(rawLine);
  }

  return {
    observations,
    recommendations,
    clinicalGuidance,
    remainingText: remainingLines.join("\n").trim(),
  };
}

function cleanInline(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("### ")) {
      elements.push(
        <h4
          key={i}
          className="text-sm font-bold mt-4 mb-1.5 text-foreground border-b border-border pb-1"
        >
          {line.slice(4)}
        </h4>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="text-base font-bold mt-5 mb-2 text-foreground">
          {line.slice(3)}
        </h3>
      );
      continue;
    }
    if (line.startsWith("# ")) {
      elements.push(
        <h2 key={i} className="text-lg font-bold mt-5 mb-2 text-foreground">
          {line.slice(2)}
        </h2>
      );
      continue;
    }

    if (/^-{3,}$/.test(line.trim()) || /^\*{3,}$/.test(line.trim())) {
      elements.push(<hr key={i} className="border-border my-3" />);
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li
          key={i}
          className="text-sm text-foreground/80 ml-4 list-disc leading-relaxed"
        >
          {renderInline(line.slice(2))}
        </li>
      );
      continue;
    }

    const numberedMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numberedMatch) {
      elements.push(
        <li
          key={i}
          className="text-sm text-foreground/80 ml-4 list-decimal leading-relaxed"
        >
          {renderInline(numberedMatch[2])}
        </li>
      );
      continue;
    }

    if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
      continue;
    }

    elements.push(
      <p
        key={i}
        className="text-sm text-foreground/80 mb-1 leading-relaxed"
      >
        {renderInline(line)}
      </p>
    );
  }

  return elements;
}

function renderInline(text: string): React.ReactNode {
  const boldParts = text.split(/\*\*(.*?)\*\*/g);
  if (boldParts.length > 1) {
    return boldParts.map((part, i) =>
      i % 2 === 1 ? (
        <strong key={i} className="font-semibold text-foreground">
          {part}
        </strong>
      ) : (
        <React.Fragment key={i}>{part}</React.Fragment>
      )
    );
  }
  return text;
}

export function ReportPanel({
  result,
  patientId,
  patientName,
  woundType,
  referringPhysician,
  referringPhysicianPhone,
  referringPhysicianEmail,
  referringPhysicianPreferredContact,
  renderBeforeSummary,
}: ReportPanelProps) {
  const [fullReportOpen, setFullReportOpen] = useState(false);
  const [referralOpen, setReferralOpen] = useState(false);
  const [referralSent, setReferralSent] = useState(false);

  const handleReferral = () => {
    setReferralOpen(true);
  };

  const parsed = useMemo<ParsedReport | null>(() => {
    if (!result) return null;
    return parseReportText(result.report_text);
  }, [result]);

  if (!result) {
    return (
      <div className="apple-card py-10 px-6">
        <div className="flex flex-col items-center text-muted-foreground">
          <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-3 ring-1 ring-border">
            <FileText className="h-7 w-7 opacity-30" />
          </div>
          <p className="text-sm font-medium mb-1">No report available</p>
          <p className="text-xs text-muted-foreground/50">
            Complete an analysis to generate a clinical report.
          </p>
        </div>
      </div>
    );
  }

  const today = formatDate(new Date().toISOString());
  // First visit (no change_score) → always show "Baseline" regardless of stored trajectory
  const effectiveTrajectory =
    result.change_score == null ? "baseline" : result.trajectory;
  const trajectoryConfig =
    TRAJECTORY_CONFIG[effectiveTrajectory] || TRAJECTORY_CONFIG.baseline;

  // BWAT total score (13-65), lower = better
  const bwatTotal = result.bwat_total ?? null;
  const hasBwat = bwatTotal != null && bwatTotal > 0;

  // Unified BWAT thresholds: 13-26 good, 27-39 moderate, 40-52 concerning, 53-65 critical
  function bwatSeverityLabel(total: number): string {
    if (total <= 26) return "Minimal";
    if (total <= 39) return "Moderate";
    if (total <= 52) return "Severe";
    return "Critical";
  }
  function bwatSeverityComment(total: number): string {
    if (total <= 26) return "Wound progressing well toward closure";
    if (total <= 39) return "Continue current care plan, monitor progress";
    if (total <= 52) return "Care plan review needed, consider specialist referral";
    return "Critical wound status — immediate clinical review required";
  }
  function bwatColor(total: number): string {
    if (total <= 26) return "text-emerald-400";
    if (total <= 39) return "text-sky-400";
    if (total <= 52) return "text-orange-300";
    return "text-rose-400";
  }
  function bwatRingColor(total: number): string {
    if (total <= 26) return "stroke-emerald-400";
    if (total <= 39) return "stroke-sky-400";
    if (total <= 52) return "stroke-orange-300";
    return "stroke-rose-400";
  }
  // Ring percent: 13=fully healed (100%), 65=worst (100% filled from worst side)
  // Invert: lower score = more of the "good" ring
  const bwatPercent = hasBwat ? Math.round(((65 - bwatTotal!) / (65 - 13)) * 100) : 0;

  // Alert styling for the healing card border
  const alertBorder =
    result.alert_level === "red"
      ? "border-rose-500/25 shadow-[0_0_24px_rgba(244,63,94,0.08)]"
      : result.alert_level === "orange"
        ? "border-orange-300/20 shadow-[0_0_20px_rgba(253,186,116,0.06)]"
        : result.alert_level === "yellow"
          ? "border-orange-300/15"
          : "border-white/[0.06]";
  // Accent bar color = BWAT severity (aligned thresholds)
  const alertAccent = hasBwat
    ? (bwatTotal! <= 26 ? "bg-emerald-500" : bwatTotal! <= 39 ? "bg-sky-400" : bwatTotal! <= 52 ? "bg-orange-300" : "bg-rose-500")
    : (result.alert_level === "red" ? "bg-rose-500" : result.alert_level === "orange" ? "bg-orange-300" : "bg-emerald-500");
  const isAlertCritical = result.alert_level === "red" || result.alert_level === "orange";
  const criticalModeHint =
    (result.alert_detail ?? "").toLowerCase().includes("critical visual flag");
  const isCriticalMode = result.critical_mode ?? criticalModeHint;
  const criticalPrimary =
    result.healing_comment ??
    result.alert_detail ??
    "Critical wound status — immediate physician review required.";
  const criticalSecondary =
    result.healing_comment ? result.alert_detail : null;

  return (
    <div className="space-y-4">
      {/* Compact header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">
            Assessment Results
          </span>
          {result.alert_level === "green" && (
            <CheckCircle className="h-4 w-4 text-emerald-500" />
          )}
        </div>
        <span className="text-xs text-muted-foreground">{today}</span>
      </div>

      {/* Referral Dialog */}
      {result.alert_level !== "green" && (
        <ReferralDialog
          open={referralOpen}
          onClose={() => setReferralOpen(false)}
          patientName={patientName ?? "Patient"}
          woundType={woundType}
          alertLevel={result.alert_level}
          alertDetail={result.alert_detail}
          referringPhysician={referringPhysician}
          referringPhysicianPhone={referringPhysicianPhone}
          referringPhysicianEmail={referringPhysicianEmail}
          referringPhysicianPreferredContact={referringPhysicianPreferredContact}
          onReferralSent={() => setReferralSent(true)}
        />
      )}

      {isCriticalMode && (
        <AlertCard
          level="red"
          detail={criticalPrimary}
          secondaryDetail={criticalSecondary}
          referralSent={referralSent}
          onReferralClick={handleReferral}
        />
      )}

      <div className={cn(isCriticalMode && "opacity-40 grayscale pointer-events-none")}>
        {/* Healing Score + Alert + Evolution Strip */}
        <div
          className={cn(
            "apple-card overflow-hidden border",
            alertBorder,
            result.alert_level === "red" && "animate-alert-pulse"
          )}
        >
          {/* Alert accent bar */}
          <div className={cn("h-[3px]", alertAccent)} />

          <div className="p-4">
            <div className="flex items-center gap-4">
              {/* Circular BWAT gauge */}
              <div className="relative shrink-0 w-20 h-20">
                <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="hsl(228 28% 22%)" strokeWidth="5" />
                  {hasBwat && (
                    <circle
                      cx="40" cy="40" r="34" fill="none"
                      className={bwatRingColor(bwatTotal!)}
                      strokeWidth="5" strokeLinecap="round"
                      strokeDasharray={`${2 * Math.PI * 34}`}
                      strokeDashoffset={`${2 * Math.PI * 34 * (1 - bwatPercent / 100)}`}
                      style={{ transition: "stroke-dashoffset 1s ease-out" }}
                    />
                  )}
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  {hasBwat ? (
                    <>
                      <span className={cn("text-xl font-bold tabular-nums leading-none", bwatColor(bwatTotal!))}>
                        {bwatTotal}
                      </span>
                      <span className="text-[9px] text-muted-foreground/60 font-medium mt-0.5">/65</span>
                    </>
                  ) : (
                    <span className="text-[11px] text-muted-foreground/40">N/A</span>
                  )}
                </div>
              </div>

              {/* Status + comment */}
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium mb-1">BWAT Score</p>
                {hasBwat ? (
                  <>
                    <p className={cn("text-[13px] font-semibold leading-tight mb-1", bwatColor(bwatTotal!))}>
                      {bwatSeverityLabel(bwatTotal!)}
                    </p>
                    <p className="text-[12px] text-muted-foreground leading-snug">
                      {isCriticalMode
                        ? "Critical alert above — review immediately."
                        : result.healing_comment || bwatSeverityComment(bwatTotal!)}
                    </p>
                  </>
                ) : (
                  <p className="text-[12px] text-muted-foreground leading-snug">
                    {result.healing_comment || "BWAT scoring not available for this assessment"}
                  </p>
                )}
              </div>
            </div>

            {/* Alert detail + referral */}
            {!isCriticalMode && result.alert_level !== "green" && (
              <div className="mt-3 pt-3 border-t border-border/20 space-y-3">
                {result.alert_detail && !result.alert_detail.includes("Contradiction") && (
                  <p className="text-[12px] text-muted-foreground/80 leading-snug">
                    {result.alert_detail}
                  </p>
                )}
                {isAlertCritical && (
                  <>
                    {referralSent ? (
                      <div className="flex items-center gap-2 text-[12px] font-semibold text-emerald-400">
                        <CheckCircle className="h-3.5 w-3.5" />
                        Referral sent successfully
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={handleReferral}
                        className={cn(
                          "w-full flex items-center justify-center gap-2 h-10 rounded-xl",
                          "text-[12px] font-semibold transition-colors active:opacity-80 ring-1",
                          result.alert_level === "red"
                            ? "bg-rose-500/15 text-rose-300 ring-rose-500/25"
                            : "bg-orange-300/10 text-orange-300 ring-orange-300/20"
                        )}
                      >
                        <Send className="h-3.5 w-3.5" />
                        Refer to Physician
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Evolution strip — bottom of card */}
          {effectiveTrajectory === "baseline" ? (
            <div className="px-4 py-2.5 bg-white/[0.03] border-t border-border/15 flex items-center gap-2">
              <Circle className="h-3 w-3 text-muted-foreground/30 shrink-0" />
              <span className="text-[11px] text-muted-foreground/40">Initial assessment &mdash; baseline established</span>
            </div>
          ) : (
            <div className="px-4 py-3 border-t border-border/15 bg-white/[0.02]">
              <div className="flex items-center justify-between mb-2">
                <div className={cn("inline-flex items-center gap-1 text-[11px] font-semibold", trajectoryConfig.color)}>
                  {trajectoryConfig.icon}
                  {trajectoryConfig.label}
                </div>
                {result.previous_visit_date && (
                  <span className="text-[10px] text-muted-foreground/35">
                    vs {formatDate(result.previous_visit_date)}
                  </span>
                )}
              </div>
              {/* Progress bar: BWAT total */}
              {hasBwat && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground/50 tabular-nums w-5 text-right shrink-0">
                    {result.previous_healing_score != null && result.previous_healing_score > 10
                      ? result.previous_healing_score
                      : ""}
                  </span>
                  <div className="flex-1 h-[6px] rounded-full bg-white/[0.06] relative overflow-hidden">
                    {/* Previous BWAT ghost */}
                    {result.previous_healing_score != null && result.previous_healing_score > 10 && (
                      <div
                        className="absolute top-0 h-full rounded-full bg-white/10"
                        style={{ width: `${((65 - result.previous_healing_score) / 52) * 100}%` }}
                      />
                    )}
                    {/* Current BWAT bar — inverted: lower BWAT = more bar */}
                    <div
                      className={cn(
                        "absolute top-0 h-full rounded-full transition-all duration-700",
                        bwatTotal! <= 26 ? "bg-emerald-400" :
                        bwatTotal! <= 39 ? "bg-sky-400" :
                        bwatTotal! <= 52 ? "bg-orange-300" :
                        "bg-rose-400"
                      )}
                      style={{ width: `${bwatPercent}%` }}
                    />
                  </div>
                  <span className={cn("text-[10px] font-semibold tabular-nums w-5 shrink-0", bwatColor(bwatTotal!))}>
                    {bwatTotal}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* BWAT Assessment — 2x2 grid */}
        <div className="flex flex-col gap-0.5 mb-1 px-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">BWAT Assessment</span>
            <span className="text-[10px] text-muted-foreground/50">Scale: 1 (best) → 5 (worst)</span>
          </div>
          <p className="text-[9px] text-muted-foreground/40 leading-tight">
            Bates-Jensen Wound Assessment Tool — 13 items, validated (ICC&nbsp;=&nbsp;0.90). Total: 13 (healed) → 65 (critical).
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(
            Object.keys(
              result.time_classification
            ) as (keyof TimeClassification)[]
          ).map((dim) => (
            <TimeScoreCard
              key={dim}
              dimension={dim}
              data={result.time_classification[dim]}
            />
          ))}
        </div>

        {/* Slot: content injected before Clinical Summary */}
        {renderBeforeSummary}

      {/* Clinical Summary removed — redundant with TIME scores + patient header */}

        {/* Clinical Guidance (Nurse Q&A) — shown before recommendations */}
        {parsed && parsed.clinicalGuidance.length > 0 && (
          <CollapsibleSection
            title="Clinical Guidance"
            icon={<MessageCircle className="h-4 w-4" />}
            defaultOpen
          >
            <div className="space-y-3 pt-3">
              <p className="text-[11px] text-muted-foreground/60 uppercase tracking-wider font-medium">
                Answers based on wound assessment
              </p>
              {parsed.clinicalGuidance.map((qa, i) => (
                <div
                  key={i}
                  className="rounded-xl overflow-hidden ring-1 ring-rose-500/15"
                >
                  {qa.question && (
                    <div className="px-4 py-2.5 bg-rose-500/10 border-b border-rose-500/10">
                      <p className="text-[13px] font-semibold text-rose-400 flex items-start gap-2">
                        <span className="shrink-0 text-rose-400/60">Q</span>
                        <span>{qa.question}?</span>
                      </p>
                    </div>
                  )}
                  <div className="px-4 py-3">
                    <p className="text-[13px] text-foreground/75 leading-[1.7] tracking-[0.01em]">
                      {qa.answer.split('. ').reduce<React.ReactNode[]>((acc, sentence, si, arr) => {
                        if (si > 0) acc.push(<span key={`br-${si}`} className="inline-block w-full h-1.5" />);
                        acc.push(<span key={`s-${si}`}>{sentence}{si < arr.length - 1 ? '.' : ''}</span>);
                        return acc;
                      }, [])}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {/* Recommendations */}
        {parsed && parsed.recommendations.length > 0 && (
          <CollapsibleSection
            title="Recommendations"
            icon={<ClipboardCheck className="h-4 w-4" />}
            defaultOpen
          >
            <div className="space-y-2 pt-3">
              {parsed.recommendations.map((rec, i) => {
                const accents = [
                  { gradient: "from-blue-500/12 to-indigo-500/6", ring: "ring-blue-500/15", num: "text-blue-400", numBg: "bg-blue-500/20" },
                  { gradient: "from-violet-500/12 to-purple-500/6", ring: "ring-violet-500/15", num: "text-violet-400", numBg: "bg-violet-500/20" },
                  { gradient: "from-cyan-500/12 to-sky-500/6", ring: "ring-cyan-500/15", num: "text-cyan-400", numBg: "bg-cyan-500/20" },
                  { gradient: "from-emerald-500/12 to-teal-500/6", ring: "ring-emerald-500/15", num: "text-emerald-400", numBg: "bg-emerald-500/20" },
                  { gradient: "from-sky-500/12 to-blue-500/6", ring: "ring-sky-500/15", num: "text-sky-400", numBg: "bg-sky-500/20" },
                ];
                const a = accents[i % accents.length];
                return (
                  <div
                    key={i}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-xl ring-1 bg-gradient-to-r",
                      a.gradient, a.ring
                    )}
                  >
                    <span className={cn(
                      "mt-0.5 w-5 h-5 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0",
                      a.numBg, a.num
                    )}>
                      {i + 1}
                    </span>
                    <p className="text-[13px] text-foreground/80 leading-relaxed">
                      {rec}
                    </p>
                  </div>
                );
              })}
            </div>
          </CollapsibleSection>
        )}

        {/* Contradiction Warning */}
        {result.contradiction_flag && result.contradiction_detail && (
          <div className="apple-card p-4 ring-1 ring-orange-300/20">
            <div className="flex items-start gap-3">
              <ShieldAlert className="h-5 w-5 text-orange-300 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Image / Audio Contradiction
                </p>
                <p className="text-[13px] text-foreground/80 mt-1 leading-relaxed">
                  {result.contradiction_detail}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Full Report */}
        <div className="apple-card overflow-hidden">
          <button
            type="button"
            onClick={() => setFullReportOpen((v) => !v)}
            className={cn(
              "w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left",
              "min-h-[48px] transition-colors"
            )}
            aria-expanded={fullReportOpen}
          >
            <div className="flex items-center gap-2.5">
              <span className="text-primary/60">
                <FileText className="h-4 w-4" />
              </span>
              <span className="text-[13px] font-semibold text-foreground">
                Full Report
              </span>
              <span className="text-[10px] text-muted-foreground/50 bg-muted px-1.5 py-0.5 rounded ring-1 ring-border">
                RAW
              </span>
            </div>
            {fullReportOpen ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground/50 shrink-0" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground/50 shrink-0" />
            )}
          </button>
          {fullReportOpen && (
            <div className="px-4 pb-4 pt-0">
              <div className="border-t border-border pt-3 max-w-none">
                {renderMarkdown(result.report_text)}
              </div>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
