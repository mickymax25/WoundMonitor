"use client";

import React from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  FileText,
  Download,
  Calendar,
  User,
  Stethoscope,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import type { AnalysisResult } from "@/lib/types";

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
    { icon: React.ReactNode; label: string; animate: boolean; borderColor: string }
  > = {
    yellow: {
      icon: <Info className="h-4 w-4 text-amber-600" />,
      label: "Advisory",
      animate: false,
      borderColor: "border-amber-400",
    },
    orange: {
      icon: <AlertCircle className="h-4 w-4 text-orange-600" />,
      label: "Warning",
      animate: false,
      borderColor: "border-orange-400",
    },
    red: {
      icon: <AlertTriangle className="h-4 w-4 text-red-600" />,
      label: "Critical Alert",
      animate: true,
      borderColor: "border-red-500",
    },
  };

  const c = config[level] || config.yellow;

  return (
    <div
      className={cn(
        "p-3 rounded-lg border-l-4 mb-4",
        level === "yellow" && "bg-amber-50 border-amber-400",
        level === "orange" && "bg-orange-50 border-orange-400",
        level === "red" && "bg-red-50 border-red-500",
        c.animate && "animate-alert-pulse"
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        {c.icon}
        <div>
          <p className={cn(
            "text-sm font-semibold",
            level === "yellow" && "text-amber-800",
            level === "orange" && "text-orange-800",
            level === "red" && "text-red-800",
          )}>
            {c.label}
          </p>
          {detail && (
            <p className={cn(
              "text-xs mt-1",
              level === "yellow" && "text-amber-700",
              level === "orange" && "text-orange-700",
              level === "red" && "text-red-700",
            )}>
              {detail}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Headers
    if (line.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="text-sm font-bold mt-4 mb-1.5 text-slate-800 border-b border-slate-200 pb-1">
          {line.slice(4)}
        </h4>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="text-base font-bold mt-5 mb-2 text-slate-900">
          {line.slice(3)}
        </h3>
      );
      continue;
    }
    if (line.startsWith("# ")) {
      elements.push(
        <h2 key={i} className="text-lg font-bold mt-5 mb-2 text-slate-900">
          {line.slice(2)}
        </h2>
      );
      continue;
    }

    // Horizontal rule
    if (/^-{3,}$/.test(line.trim()) || /^\*{3,}$/.test(line.trim())) {
      elements.push(
        <hr key={i} className="border-slate-200 my-3" />
      );
      continue;
    }

    // Bullet points
    if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="text-sm text-slate-700 ml-4 list-disc leading-relaxed">
          {renderInline(line.slice(2))}
        </li>
      );
      continue;
    }

    // Numbered lists
    const numberedMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numberedMatch) {
      elements.push(
        <li key={i} className="text-sm text-slate-700 ml-4 list-decimal leading-relaxed">
          {renderInline(numberedMatch[2])}
        </li>
      );
      continue;
    }

    // Empty lines
    if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
      continue;
    }

    // Paragraph
    elements.push(
      <p key={i} className="text-sm text-slate-700 mb-1 leading-relaxed">
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
        <strong key={i} className="font-semibold text-slate-900">
          {renderCode(part)}
        </strong>
      ) : (
        <React.Fragment key={i}>{renderCode(part)}</React.Fragment>
      )
    );
  }
  return renderCode(text);
}

function renderCode(text: string): React.ReactNode {
  const parts = text.split(/`([^`]+)`/g);
  if (parts.length <= 1) return text;
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <code
        key={i}
        className="px-1.5 py-0.5 rounded bg-slate-100 text-xs font-mono text-teal-700 border border-slate-200"
      >
        {part}
      </code>
    ) : (
      part
    )
  );
}

export function ReportPanel({ result, patientName, woundType }: ReportPanelProps) {
  if (!result) {
    return (
      <Card className="border-border/60 shadow-lg shadow-black/10">
        <CardContent className="py-10">
          <div className="flex flex-col items-center text-muted-foreground">
            <div className="w-14 h-14 rounded-xl bg-accent/50 flex items-center justify-center mb-3 border border-border">
              <FileText className="h-7 w-7 opacity-40" />
            </div>
            <p className="text-sm font-medium mb-1">No report available</p>
            <p className="text-xs text-muted-foreground/60">
              Complete an analysis to generate a clinical report.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const today = formatDate(new Date().toISOString());

  return (
    <Card className="border-border/60 shadow-lg shadow-black/10 overflow-hidden">
      {/* Report header bar */}
      <div className="px-6 py-4 bg-card border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          <span className="text-base font-semibold text-foreground">
            Clinical Report
          </span>
          {result.alert_level === "green" && (
            <CheckCircle className="h-4 w-4 text-emerald-500" />
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 text-xs border-border/60"
          onClick={() => {
            // PDF download placeholder
          }}
        >
          <Download className="h-3.5 w-3.5" />
          Download PDF
        </Button>
      </div>

      {/* Report document (light background) */}
      <div className="report-document p-6 md:p-8">
        {/* Document header */}
        <div className="mb-5 pb-4 border-b border-slate-200">
          <h2 className="text-lg font-bold text-slate-900 mb-3">
            Wound Assessment Report
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            {patientName && (
              <div className="flex items-center gap-1.5 text-slate-600">
                <User className="h-3.5 w-3.5 text-slate-400" />
                <span className="font-medium text-slate-800">{patientName}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-slate-600">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-medium text-slate-800">{today}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-600">
              <Stethoscope className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-medium text-slate-800">
                {woundTypeLabel(woundType)}
              </span>
            </div>
          </div>
        </div>

        {/* Alert Banner */}
        <AlertBanner
          level={result.alert_level}
          detail={result.alert_detail}
        />

        {/* Contradiction Warning */}
        {result.contradiction_flag && result.contradiction_detail && (
          <div className="p-3 rounded-lg border-l-4 border-amber-400 bg-amber-50 mb-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-amber-800">
                  Image/Audio Contradiction
                </p>
                <p className="text-xs text-amber-700 mt-1">
                  {result.contradiction_detail}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Report Body */}
        <div className="max-w-none">
          {renderMarkdown(result.report_text)}
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-200">
          <p className="text-[10px] text-slate-400 text-center">
            Generated by WoundChrono AI -- MedGemma + MedSigLIP + MedASR Pipeline.
            This report is for clinical decision support and does not constitute a diagnosis.
          </p>
        </div>
      </div>
    </Card>
  );
}
