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
} from "lucide-react";
import { TimeScoreCard } from "@/components/TimeScoreCard";
import { ReferralDialog } from "@/components/ReferralDialog";
import { cn, formatDate } from "@/lib/utils";
import type { AnalysisResult, TimeClassification, Referral } from "@/lib/types";

interface ReportPanelProps {
  result: AnalysisResult | null;
  patientId?: string | null;
  patientName?: string | null;
  woundType?: string | null;
  referringPhysician?: string | null;
  referringPhysicianPhone?: string | null;
  referringPhysicianEmail?: string | null;
  referringPhysicianPreferredContact?: string | null;
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
  referralSent,
  onReferralClick,
}: {
  level: string;
  detail: string | null;
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
  remainingText: string;
}

function parseReportText(reportText: string): ParsedReport {
  const lines = reportText.split("\n");
  const observations: { label: string; text: string }[] = [];
  const recommendations: string[] = [];
  const remainingLines: string[] = [];

  let inRecommendations = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

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
}: ReportPanelProps) {
  const [fullReportOpen, setFullReportOpen] = useState(false);
  const [referralOpen, setReferralOpen] = useState(false);
  const [referralSent, setReferralSent] = useState(false);

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
  const trajectoryConfig =
    TRAJECTORY_CONFIG[result.trajectory] || TRAJECTORY_CONFIG.baseline;

  // Healing score: average of 4 TIME dimensions, shown as 1-10
  const timeScores = Object.values(result.time_classification);
  const compositeRaw = timeScores.reduce((sum, d) => sum + d.score, 0) / timeScores.length;
  const healingScore = Math.max(1, Math.min(10, Math.round(compositeRaw * 10)));
  const healingPercent = Math.round(compositeRaw * 100);

  function healingColor(score: number): string {
    if (score >= 7) return "text-emerald-500";
    if (score >= 4) return "text-orange-300";
    return "text-rose-400";
  }
  function healingRingColor(score: number): string {
    if (score >= 7) return "stroke-emerald-400";
    if (score >= 4) return "stroke-orange-300";
    return "stroke-rose-400";
  }
  function healingLabel(score: number): string {
    if (score >= 8) return "Healing well — wound is progressing";
    if (score >= 6) return "Progressing — continue current care";
    if (score >= 4) return "Needs attention — consider care plan review";
    if (score >= 2) return "Poor healing — intervention recommended";
    return "Critical — urgent attention required";
  }

  // Alert styling for the healing card border
  const alertBorder =
    result.alert_level === "red"
      ? "border-rose-500/25 shadow-[0_0_24px_rgba(244,63,94,0.08)]"
      : result.alert_level === "orange"
        ? "border-orange-300/20 shadow-[0_0_20px_rgba(253,186,116,0.06)]"
        : result.alert_level === "yellow"
          ? "border-orange-300/15"
          : "border-white/[0.06]";
  const alertAccent =
    result.alert_level === "red"
      ? "bg-rose-500"
      : result.alert_level === "orange"
        ? "bg-orange-300"
        : result.alert_level === "yellow"
          ? "bg-orange-300"
          : "bg-emerald-500";
  const isAlertCritical = result.alert_level === "red" || result.alert_level === "orange";

  return (
    <div className="space-y-4 animate-fade-in-up">
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
      {result.alert_level !== "green" && patientId && (
        <ReferralDialog
          open={referralOpen}
          onClose={() => setReferralOpen(false)}
          assessmentId={result.assessment_id}
          patientId={patientId}
          patientName={patientName ?? "Patient"}
          alertLevel={result.alert_level}
          alertDetail={result.alert_detail}
          referringPhysician={referringPhysician}
          referringPhysicianPhone={referringPhysicianPhone}
          referringPhysicianEmail={referringPhysicianEmail}
          referringPhysicianPreferredContact={referringPhysicianPreferredContact}
          onReferralCreated={() => {
            setReferralSent(true);
          }}
        />
      )}

      {/* Healing Score + Trajectory + Alert — unified card */}
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
            {/* Circular healing gauge */}
            <div className="relative shrink-0 w-20 h-20">
              <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
                <circle
                  cx="40" cy="40" r="34"
                  fill="none"
                  stroke="hsl(228 28% 22%)"
                  strokeWidth="5"
                />
                <circle
                  cx="40" cy="40" r="34"
                  fill="none"
                  className={healingRingColor(healingScore)}
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 34}`}
                  strokeDashoffset={`${2 * Math.PI * 34 * (1 - healingPercent / 100)}`}
                  style={{ transition: "stroke-dashoffset 1s ease-out" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn("text-xl font-bold tabular-nums leading-none", healingColor(healingScore))}>
                  {healingScore}
                </span>
                <span className="text-[9px] text-muted-foreground/60 font-medium mt-0.5">/10</span>
              </div>
            </div>

            {/* Trajectory + description */}
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium mb-1">Healing Score</p>
              <div
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold mb-1.5",
                  trajectoryConfig.bg,
                  trajectoryConfig.color
                )}
              >
                {trajectoryConfig.icon}
                {trajectoryConfig.label}
              </div>
              <p className="text-[12px] text-muted-foreground leading-snug">
                {healingLabel(healingScore)}
              </p>
            </div>
          </div>

          {/* Alert detail + referral — inline, compact */}
          {result.alert_level !== "green" && (
            <div className="mt-3 pt-3 border-t border-border/20 space-y-3">
              {result.alert_detail && (
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
                      onClick={() => setReferralOpen(true)}
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
      </div>

      {/* TIME Assessment — 2x2 grid */}
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">TIME Assessment</span>
        <span className="text-[10px] text-muted-foreground/50">Scale: 1 (critical) → 10 (healed)</span>
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

      {/* Clinical Summary */}
      {parsed && parsed.observations.length > 0 && (
        <CollapsibleSection
          title="Clinical Summary"
          icon={<Stethoscope className="h-4 w-4" />}
          defaultOpen
        >
          <ul className="space-y-3 pt-3">
            {parsed.observations.map((obs, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary/60 shrink-0" />
                <p className="text-sm text-foreground/80 leading-relaxed">
                  <strong className="font-semibold text-foreground">
                    {obs.label}:
                  </strong>{" "}
                  {obs.text}
                </p>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Recommendations */}
      {parsed && parsed.recommendations.length > 0 && (
        <CollapsibleSection
          title="Recommendations"
          icon={<ClipboardCheck className="h-4 w-4" />}
          defaultOpen
        >
          <ul className="space-y-2.5 pt-3">
            {parsed.recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-3 min-h-[44px]">
                <div className="mt-0.5 h-5 w-5 rounded border border-primary/30 bg-primary/5 flex items-center justify-center shrink-0">
                  <CheckCircle className="h-3 w-3 text-primary/50" />
                </div>
                <p className="text-sm text-foreground/80 leading-relaxed pt-0.5">
                  {rec}
                </p>
              </li>
            ))}
          </ul>
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

      {/* Footer / Disclaimer */}
      <div className="flex items-start gap-2.5 px-2 py-3">
        <Bot className="h-4 w-4 text-muted-foreground/40 mt-0.5 shrink-0" />
        <p className="text-xs text-muted-foreground/60 leading-relaxed">
          AI-generated report -- Wound Monitor (MedGemma + MedSigLIP + MedASR).
          For clinical decision support only. Does not constitute a diagnosis.
        </p>
      </div>
    </div>
  );
}
