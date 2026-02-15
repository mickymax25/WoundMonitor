"use client";

import React from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  FileText,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, alertBgColor } from "@/lib/utils";
import type { AnalysisResult } from "@/lib/types";

interface ReportPanelProps {
  result: AnalysisResult | null;
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
    { icon: React.ReactNode; label: string; animate: boolean }
  > = {
    yellow: {
      icon: <Info className="h-4 w-4 text-amber-400" />,
      label: "Advisory",
      animate: false,
    },
    orange: {
      icon: <AlertCircle className="h-4 w-4 text-orange-400" />,
      label: "Warning",
      animate: false,
    },
    red: {
      icon: <AlertTriangle className="h-4 w-4 text-red-400" />,
      label: "Critical Alert",
      animate: true,
    },
  };

  const c = config[level] || config.yellow;

  return (
    <div
      className={cn(
        "p-3 rounded-lg border mb-4",
        alertBgColor(level),
        c.animate && "animate-alert-pulse"
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        {c.icon}
        <div>
          <p className="text-sm font-medium">{c.label}</p>
          {detail && (
            <p className="text-xs mt-1 opacity-80">{detail}</p>
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
        <h4 key={i} className="text-sm font-semibold mt-3 mb-1">
          {line.slice(4)}
        </h4>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="text-base font-semibold mt-4 mb-1">
          {line.slice(3)}
        </h3>
      );
      continue;
    }
    if (line.startsWith("# ")) {
      elements.push(
        <h2 key={i} className="text-lg font-semibold mt-4 mb-2">
          {line.slice(2)}
        </h2>
      );
      continue;
    }

    // Horizontal rule
    if (/^-{3,}$/.test(line.trim()) || /^\*{3,}$/.test(line.trim())) {
      elements.push(
        <hr key={i} className="border-border my-3" />
      );
      continue;
    }

    // Bullet points
    if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="text-sm text-foreground/90 ml-4 list-disc">
          {renderInline(line.slice(2))}
        </li>
      );
      continue;
    }

    // Numbered lists (e.g. "1. ", "12. ")
    const numberedMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numberedMatch) {
      elements.push(
        <li key={i} className="text-sm text-foreground/90 ml-4 list-decimal">
          {renderInline(numberedMatch[2])}
        </li>
      );
      continue;
    }

    // Empty lines
    if (line.trim() === "") {
      elements.push(<br key={i} />);
      continue;
    }

    // Paragraph
    elements.push(
      <p key={i} className="text-sm text-foreground/90 mb-1">
        {renderInline(line)}
      </p>
    );
  }

  return elements;
}

function renderInline(text: string): React.ReactNode {
  // Split on bold (**) and inline code (`) patterns
  // Process bold first, then inline code within each segment
  const boldParts = text.split(/\*\*(.*?)\*\*/g);
  if (boldParts.length > 1) {
    return boldParts.map((part, i) =>
      i % 2 === 1 ? (
        <strong key={i} className="font-semibold text-foreground">
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
        className="px-1.5 py-0.5 rounded bg-accent text-xs font-mono text-primary"
      >
        {part}
      </code>
    ) : (
      part
    )
  );
}

export function ReportPanel({ result }: ReportPanelProps) {
  if (!result) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex flex-col items-center text-muted-foreground">
            <FileText className="h-8 w-8 mb-2 opacity-40" />
            <p className="text-sm">No report available.</p>
            <p className="text-xs mt-1">
              Complete an analysis to generate a clinical report.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          Clinical Report
          {result.alert_level === "green" && (
            <CheckCircle className="h-4 w-4 text-emerald-500 ml-auto" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <AlertBanner
          level={result.alert_level}
          detail={result.alert_detail}
        />

        {result.contradiction_flag && result.contradiction_detail && (
          <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 mb-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-400">
                  Image/Audio Contradiction
                </p>
                <p className="text-xs text-amber-400/80 mt-1">
                  {result.contradiction_detail}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="prose-sm max-w-none">
          {renderMarkdown(result.report_text)}
        </div>
      </CardContent>
    </Card>
  );
}
