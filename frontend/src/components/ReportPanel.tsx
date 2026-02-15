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
} from "lucide-react";
import { TimeScoreCard } from "@/components/TimeScoreCard";
import { cn, formatDate } from "@/lib/utils";
import type { AnalysisResult, TimeClassification } from "@/lib/types";

interface ReportPanelProps {
  result: AnalysisResult | null;
  patientName?: string | null;
  woundType?: string | null;
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

function AlertBanner({
  level,
  detail,
}: {
  level: string;
  detail: string | null;
}) {
  if (level === "green") return null;

  const config: Record<
    string,
    {
      icon: React.ReactNode;
      label: string;
      animate: boolean;
      bg: string;
      text: string;
      border: string;
    }
  > = {
    yellow: {
      icon: <Info className="h-5 w-5 text-orange-400" />,
      label: "Advisory",
      animate: false,
      bg: "bg-orange-500/8",
      text: "text-orange-300",
      border: "border-orange-500/15",
    },
    orange: {
      icon: <AlertCircle className="h-5 w-5 text-orange-400" />,
      label: "Warning",
      animate: false,
      bg: "bg-orange-500/8",
      text: "text-orange-300",
      border: "border-orange-500/15",
    },
    red: {
      icon: <AlertTriangle className="h-5 w-5 text-rose-400" />,
      label: "Critical Alert",
      animate: true,
      bg: "bg-rose-500/8",
      text: "text-rose-300",
      border: "border-rose-500/15",
    },
  };

  const c = config[level] || config.yellow;

  return (
    <div
      className={cn(
        "p-4 rounded-xl border",
        c.bg,
        c.border,
        c.animate && "animate-alert-pulse"
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">{c.icon}</div>
        <div className="min-w-0">
          <p className={cn("text-base font-bold", c.text)}>{c.label}</p>
          {detail && (
            <p className={cn("text-sm mt-1 opacity-80", c.text)}>
              {detail}
            </p>
          )}
        </div>
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
          className="text-sm text-muted-foreground ml-4 list-disc leading-relaxed"
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
          className="text-sm text-muted-foreground ml-4 list-decimal leading-relaxed"
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
        className="text-sm text-muted-foreground mb-1 leading-relaxed"
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
  patientName,
  woundType,
}: ReportPanelProps) {
  const [fullReportOpen, setFullReportOpen] = useState(false);

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

  // Global wound health score (0-100) — normalized composite of TIME dimensions
  const timeScores = Object.values(result.time_classification);
  const compositeRaw = timeScores.reduce((sum, d) => sum + d.score, 0) / timeScores.length;
  const globalScore = Math.round(compositeRaw * 100);

  function globalScoreColor(score: number): string {
    if (score >= 70) return "text-emerald-500";
    if (score >= 40) return "text-orange-400";
    return "text-rose-400";
  }
  function globalScoreRingColor(score: number): string {
    if (score >= 70) return "stroke-emerald-400";
    if (score >= 40) return "stroke-orange-400";
    return "stroke-rose-400";
  }
  function globalScoreLabel(score: number): string {
    if (score >= 80) return "Good condition";
    if (score >= 60) return "Fair condition";
    if (score >= 40) return "Needs attention";
    if (score >= 20) return "Poor condition";
    return "Critical";
  }

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

      {/* Alert Banner */}
      <AlertBanner level={result.alert_level} detail={result.alert_detail} />

      {/* Global Score + Trajectory */}
      <div className="apple-card p-4">
        <div className="flex items-center gap-4">
          {/* Circular score gauge */}
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
                className={globalScoreRingColor(globalScore)}
                strokeWidth="5"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 34}`}
                strokeDashoffset={`${2 * Math.PI * 34 * (1 - globalScore / 100)}`}
                style={{ transition: "stroke-dashoffset 1s ease-out" }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={cn("text-xl font-bold tabular-nums leading-none", globalScoreColor(globalScore))}>
                {globalScore}
              </span>
              <span className="text-[9px] text-muted-foreground/60 font-medium mt-0.5">/100</span>
            </div>
          </div>

          {/* Trajectory + description */}
          <div className="flex-1 min-w-0">
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
            <p className="text-[13px] text-muted-foreground leading-snug">
              {globalScoreLabel(globalScore)}
              {result.trajectory !== "baseline" && result.change_score !== null && (
                <>
                  {" — "}
                  {result.change_score < 0.1
                    ? "minimal change since last visit"
                    : result.change_score < 0.3
                      ? "slight change since last visit"
                      : "significant change since last visit"}
                </>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* TIME Assessment — 2x2 grid */}
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
                <p className="text-sm text-muted-foreground leading-relaxed">
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
                <p className="text-sm text-muted-foreground leading-relaxed pt-0.5">
                  {rec}
                </p>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Contradiction Warning */}
      {result.contradiction_flag && result.contradiction_detail && (
        <div className="apple-card p-4 ring-1 ring-orange-500/20">
          <div className="flex items-start gap-3">
            <ShieldAlert className="h-5 w-5 text-orange-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                Image / Audio Contradiction
              </p>
              <p className="text-[13px] text-muted-foreground mt-1 leading-relaxed">
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
          AI-generated report -- WoundChrono (MedGemma + MedSigLIP + MedASR).
          For clinical decision support only. Does not constitute a diagnosis.
        </p>
      </div>
    </div>
  );
}
