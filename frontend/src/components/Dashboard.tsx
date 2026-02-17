"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  Stethoscope,
  Activity,
  Heart,
  RefreshCw,
  AlertCircle,
  ChevronRight,
  FileText,
  TrendingUp,
  TrendingDown,
  Minus,
  Search,
  Plus,
  AlertTriangle,
  Shield,
  Zap,
  Clock,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { NewPatientDialog } from "@/components/NewPatientDialog";
import { AssessmentPanel } from "@/components/AssessmentPanel";
import { TimelineChart } from "@/components/TimelineChart";
import { ReportPanel } from "@/components/ReportPanel";
import { AssessmentHistory } from "@/components/AssessmentHistory";
import { PatientList } from "@/components/PatientList";
import { SettingsPanel } from "@/components/SettingsPanel";
import { listPatients, listPatientAssessments } from "@/lib/api";
import { cn, alertDotColor } from "@/lib/utils";
import type { PatientResponse, AssessmentResponse, AnalysisResult, MobileTab } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function woundLabel(type: string | null, location: string | null): string {
  const parts = [type, location]
    .filter(Boolean)
    .map((s) =>
      s!
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase())
    );
  return parts.join(" — ") || "No wound details";
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((p) => p.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function TrajectoryBadge({ trajectory }: { trajectory: string | null }) {
  const config: Record<string, { icon: React.ReactNode; label: string; cls: string }> = {
    improving: { icon: <TrendingUp className="h-3 w-3" />, label: "Improving", cls: "text-emerald-400 bg-emerald-500/10 ring-1 ring-emerald-500/15" },
    stable: { icon: <Minus className="h-3 w-3" />, label: "Stable", cls: "text-sky-400 bg-sky-500/10 ring-1 ring-sky-500/15" },
    deteriorating: { icon: <TrendingDown className="h-3 w-3" />, label: "Worsening", cls: "text-rose-400 bg-rose-500/10 ring-1 ring-rose-500/15" },
  };
  const c = trajectory ? config[trajectory] : null;
  if (!c) return null;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full", c.cls)}>
      {c.icon}
      {c.label}
    </span>
  );
}

function needsAttention(patient: PatientResponse): boolean {
  return (
    patient.latest_trajectory === "deteriorating" ||
    patient.latest_alert_level === "red" ||
    patient.latest_alert_level === "orange"
  );
}

function relativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

// ---------------------------------------------------------------------------
// Tab bar configuration
// ---------------------------------------------------------------------------

interface TabDefinition {
  id: MobileTab;
  label: string;
  icon: React.ElementType;
}

const MOBILE_TABS: TabDefinition[] = [
  { id: "patients", label: "Patients", icon: Users },
  { id: "reports", label: "Dashboard", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings2 },
];

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function Dashboard({ onSignOut }: { onSignOut?: () => void }) {
  const [patients, setPatients] = useState<PatientResponse[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientFetchError, setPatientFetchError] = useState<string | null>(null);
  const [selectedPatient, setSelectedPatient] = useState<PatientResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [trajectoryRefresh, setTrajectoryRefresh] = useState(0);

  // Mobile tab navigation
  const [activeTab, setActiveTab] = useState<MobileTab>("patients");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAssessForm, setShowAssessForm] = useState(false);

  const fetchPatients = useCallback(async () => {
    setLoadingPatients(true);
    setPatientFetchError(null);
    try {
      const data = await listPatients();
      setPatients(data);
    } catch (err) {
      setPatientFetchError(err instanceof Error ? err.message : "Failed to load patients.");
    } finally {
      setLoadingPatients(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const handleSelectPatient = useCallback(
    async (patient: PatientResponse) => {
      setSelectedPatient(patient);
      setAnalysisResult(null);
      setShowAssessForm(false);
      setTrajectoryRefresh((r) => r + 1);
      // Navigate to report tab after selecting a patient on mobile
      setActiveTab("reports");

      try {
        const assessments = await listPatientAssessments(patient.id);
        const analyzed = assessments
          .filter((a) => a.time_classification !== null)
          .sort((a, b) => new Date(b.visit_date).getTime() - new Date(a.visit_date).getTime());
        if (analyzed.length > 0) {
          const latest = analyzed[0];
          setAnalysisResult({
            assessment_id: latest.id,
            time_classification: latest.time_classification!,
            zeroshot_scores: latest.zeroshot_scores ?? {},
            trajectory: latest.trajectory ?? "baseline",
            change_score: latest.change_score ?? null,
            contradiction_flag: latest.contradiction_flag ?? false,
            contradiction_detail: latest.contradiction_detail ?? null,
            report_text: latest.report_text ?? "",
            alert_level: latest.alert_level ?? "green",
            alert_detail: latest.alert_detail ?? null,
          });
        }
      } catch {
        // Silently fail
      }
    },
    []
  );

  const handlePatientCreated = useCallback((patient: PatientResponse) => {
    setPatients((prev) => [patient, ...prev]);
    setSelectedPatient(patient);
    setAnalysisResult(null);
    setShowAssessForm(false);
    setActiveTab("reports");
  }, []);

  const handleStartAssessment = useCallback(
    async (patient: PatientResponse) => {
      setSelectedPatient(patient);
      setShowAssessForm(true);
      setActiveTab("reports");
      setTrajectoryRefresh((r) => r + 1);

      // Load existing analysis results (same logic as handleSelectPatient)
      try {
        const assessments = await listPatientAssessments(patient.id);
        const analyzed = assessments
          .filter((a) => a.time_classification !== null)
          .sort((a, b) => new Date(b.visit_date).getTime() - new Date(a.visit_date).getTime());
        if (analyzed.length > 0) {
          const latest = analyzed[0];
          setAnalysisResult({
            assessment_id: latest.id,
            time_classification: latest.time_classification!,
            zeroshot_scores: latest.zeroshot_scores ?? {},
            trajectory: latest.trajectory ?? "baseline",
            change_score: latest.change_score ?? null,
            contradiction_flag: latest.contradiction_flag ?? false,
            contradiction_detail: latest.contradiction_detail ?? null,
            report_text: latest.report_text ?? "",
            alert_level: latest.alert_level ?? "green",
            alert_detail: latest.alert_detail ?? null,
          });
        }
      } catch {
        // Silently fail — dashboard will show without previous results
      }
    },
    []
  );

  const handleAnalysisComplete = useCallback(
    (result: AnalysisResult) => {
      setAnalysisResult(result);
      setTrajectoryRefresh((r) => r + 1);
      setShowAssessForm(false);
      fetchPatients();
      setActiveTab("reports");
    },
    [fetchPatients]
  );

  // Map an AssessmentResponse (from history list) into the AnalysisResult shape
  // consumed by ReportPanel. Mirrors the mapping in handleSelectPatient.
  const handleSelectHistoryAssessment = useCallback(
    (a: AssessmentResponse) => {
      if (!a.time_classification) return;
      setAnalysisResult({
        assessment_id: a.id,
        time_classification: a.time_classification,
        zeroshot_scores: a.zeroshot_scores ?? {},
        trajectory: a.trajectory ?? "baseline",
        change_score: a.change_score ?? null,
        contradiction_flag: a.contradiction_flag ?? false,
        contradiction_detail: a.contradiction_detail ?? null,
        report_text: a.report_text ?? "",
        alert_level: a.alert_level ?? "green",
        alert_detail: a.alert_detail ?? null,
      });
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Mobile: Patients Tab
  // ---------------------------------------------------------------------------

  function MobilePatientsTab() {
    const q = searchQuery.toLowerCase();
    const filtered = patients.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.wound_type ?? "").toLowerCase().includes(q) ||
        (p.wound_location ?? "").toLowerCase().includes(q)
    );

    const priorityWeight = (p: PatientResponse): number => {
      let w = 0;
      if (p.latest_trajectory === "deteriorating") w += 100;
      if (p.latest_alert_level === "red") w += 80;
      if (p.latest_alert_level === "orange") w += 40;
      if (p.latest_alert_level === "yellow") w += 10;
      return w;
    };
    const smartSort = (a: PatientResponse, b: PatientResponse) => {
      const wDiff = priorityWeight(b) - priorityWeight(a);
      if (wDiff !== 0) return wDiff;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    };

    const attentionPatients = filtered.filter(needsAttention).sort(smartSort);
    const otherPatients = filtered.filter((p) => !needsAttention(p)).sort(smartSort);

    const totalCritical = patients.filter(
      (p) => p.latest_alert_level === "red" || p.latest_alert_level === "orange"
    ).length;
    const totalImproving = patients.filter(
      (p) => p.latest_trajectory === "improving"
    ).length;
    const totalStable = patients.filter(
      (p) => p.latest_trajectory === "stable"
    ).length;
    const totalNeedingAttention = patients.filter(needsAttention).length;
    const totalAssessments = patients.reduce((s, p) => s + p.assessment_count, 0);

    const hour = new Date().getHours();
    const greeting =
      hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    const dateStr = new Date().toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });

    // Avatar gradient on dark surface
    function avatarGradient(patient: PatientResponse, urgent?: boolean): string {
      if (urgent && patient.latest_alert_level === "red")
        return "bg-gradient-to-br from-rose-500/20 to-rose-600/10 text-rose-400 ring-1 ring-rose-500/20";
      if (urgent)
        return "bg-gradient-to-br from-orange-300/20 to-orange-600/10 text-orange-300 ring-1 ring-orange-300/20";
      if (patient.latest_trajectory === "improving")
        return "bg-gradient-to-br from-emerald-500/20 to-teal-600/10 text-emerald-400 ring-1 ring-emerald-500/20";
      if (patient.latest_trajectory === "stable")
        return "bg-gradient-to-br from-blue-500/15 to-indigo-600/10 text-blue-400 ring-1 ring-blue-500/15";
      return "bg-gradient-to-br from-slate-500/15 to-slate-600/10 text-slate-400 ring-1 ring-slate-500/15";
    }

    // Alert accent line color
    function accentColor(level: string | null): string {
      switch (level) {
        case "red": return "bg-rose-500";
        case "orange": return "bg-orange-300";
        case "yellow": return "bg-orange-300";
        case "green": return "bg-emerald-500";
        default: return "bg-slate-600";
      }
    }

    // ---- Patient card ----
    function PatientCard({ patient, urgent, index }: { patient: PatientResponse; urgent?: boolean; index: number }) {
      const isSelected = selectedPatient?.id === patient.id;
      return (
        <div
          className={cn(
            "w-full text-left overflow-hidden transition-colors",
            isSelected ? "bg-primary/5" : ""
          )}
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <div className="flex">
            {/* Accent line */}
            <div className={cn("w-[3px] shrink-0 rounded-l-[18px]", accentColor(patient.latest_alert_level))} />

            <div className="flex-1 flex items-start gap-3.5 p-4">
              {/* Avatar — tappable to go to dashboard */}
              <button
                type="button"
                onClick={() => handleSelectPatient(patient)}
                className="relative shrink-0 active:scale-95 transition-transform"
              >
                <div
                  className={cn(
                    "w-12 h-12 rounded-2xl flex items-center justify-center text-[13px] font-bold tracking-wide",
                    avatarGradient(patient, urgent)
                  )}
                >
                  {getInitials(patient.name)}
                </div>
                {/* Status dot */}
                <span
                  className={cn(
                    "absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-[2.5px]",
                    "border-[var(--surface-1)]",
                    alertDotColor(patient.latest_alert_level)
                  )}
                />
              </button>

              {/* Content — tappable to go to dashboard */}
              <button
                type="button"
                onClick={() => handleSelectPatient(patient)}
                className="flex-1 min-w-0 text-left active:opacity-70 transition-opacity"
              >
                {/* Name row */}
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-[15px] font-bold text-foreground truncate leading-tight tracking-tight">
                    {patient.name}
                  </p>
                  <span className="text-[11px] text-muted-foreground/60 shrink-0 tabular-nums flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    {relativeTime(patient.created_at)}
                  </span>
                </div>

                {/* Wound info — higher contrast */}
                <p className="text-[13px] text-foreground/50 truncate mt-1.5 leading-tight">
                  {woundLabel(patient.wound_type, patient.wound_location)}
                  {patient.age ? <span className="text-foreground/30"> · {patient.age}y</span> : ""}
                </p>

                {/* Badges row — more spacing */}
                <div className="flex items-center gap-2 mt-2.5 flex-wrap">
                  <TrajectoryBadge trajectory={patient.latest_trajectory} />
                  {patient.comorbidities.length > 0 && (
                    <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full ring-1 ring-violet-500/15">
                      {patient.comorbidities.length} comorb.
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground/40 ml-auto tabular-nums">
                    {patient.assessment_count} visit{patient.assessment_count !== 1 ? "s" : ""}
                  </span>
                </div>
              </button>

            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="h-full flex flex-col relative wc-hero">
        {/* ---- HEADER ZONE ---- */}
        <div className="shrink-0 px-5 pt-3 pb-4 relative">
          {/* Greeting */}
          <div className="animate-slide-up" style={{ animationDelay: "0ms" }}>
            <div className="flex items-baseline justify-between">
              <h2 className="text-[26px] font-bold text-foreground tracking-tight leading-none">
                {greeting}
              </h2>
              {!loadingPatients && patients.length > 0 && (
                <span className="text-[11px] text-muted-foreground tabular-nums font-medium">
                  {dateStr}
                </span>
              )}
            </div>
            {!loadingPatients && patients.length > 0 && (
              <p className="text-[13px] text-muted-foreground mt-1.5">
                {patients.length} patient{patients.length !== 1 ? "s" : ""} on file · {totalAssessments} assessment{totalAssessments !== 1 ? "s" : ""}
              </p>
            )}
          </div>

          {/* Metric pills */}
          {!loadingPatients && patients.length > 0 && (
            <div className="grid grid-cols-3 gap-2 mt-4 animate-slide-up" style={{ animationDelay: "80ms" }}>
              <div className={cn("metric-pill px-3 py-3 text-center", totalCritical > 0 && "glow-rose")}>
                <p className={cn("text-[22px] font-bold leading-none tabular-nums", totalCritical > 0 ? "text-rose-400" : "text-muted-foreground/30")}>
                  {totalCritical}
                </p>
                <p className={cn("text-[9px] mt-1 font-semibold uppercase tracking-[0.08em]", totalCritical > 0 ? "text-rose-400/60" : "text-muted-foreground/30")}>
                  Critical
                </p>
              </div>
              <div className={cn("metric-pill px-3 py-3 text-center", totalImproving > 0 && "glow-emerald")}>
                <p className={cn("text-[22px] font-bold leading-none tabular-nums", totalImproving > 0 ? "text-emerald-400" : "text-muted-foreground/30")}>
                  {totalImproving}
                </p>
                <p className={cn("text-[9px] mt-1 font-semibold uppercase tracking-[0.08em]", totalImproving > 0 ? "text-emerald-400/60" : "text-muted-foreground/30")}>
                  Healing
                </p>
              </div>
              <div className={cn("metric-pill px-3 py-3 text-center", totalStable > 0 && "glow-blue")}>
                <p className={cn("text-[22px] font-bold leading-none tabular-nums", totalStable > 0 ? "text-sky-400" : "text-muted-foreground/30")}>
                  {totalStable}
                </p>
                <p className={cn("text-[9px] mt-1 font-semibold uppercase tracking-[0.08em]", totalStable > 0 ? "text-sky-400/60" : "text-muted-foreground/30")}>
                  Stable
                </p>
              </div>
            </div>
          )}

        </div>

        {/* ---- SCROLLABLE CONTENT ---- */}
        <div className="flex-1 overflow-y-auto px-4 pb-24">
          {/* Search + Actions — inside scroll area */}
          {!loadingPatients && patients.length > 0 && (
            <div className="apple-card p-3 mb-4 animate-slide-up" style={{ animationDelay: "160ms" }}>
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search patients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-10 pl-10 pr-4 text-[13px] text-foreground bg-[var(--surface-2)] rounded-xl
                             placeholder:text-muted-foreground/40 border border-border/30
                             focus:outline-none focus:ring-1 focus:ring-primary/30"
                />
              </div>
              <div className="flex gap-2 mt-2.5">
                <NewPatientDialog
                  onCreated={handlePatientCreated}
                  trigger={
                    <button
                      type="button"
                      className="flex-1 flex items-center justify-center gap-2 h-10 rounded-xl
                                 bg-primary/15 text-primary text-[13px] font-semibold
                                 ring-1 ring-primary/20
                                 active:bg-primary/25 transition-colors"
                    >
                      <Plus className="h-4 w-4" />
                      New Patient
                    </button>
                  }
                />
                {selectedPatient && (
                  <button
                    type="button"
                    onClick={() => handleStartAssessment(selectedPatient)}
                    className="flex-1 flex items-center justify-center gap-2 h-10 rounded-xl
                               bg-emerald-500/15 text-emerald-400 text-[13px] font-semibold
                               ring-1 ring-emerald-500/20
                               active:bg-emerald-500/25 transition-colors"
                  >
                    <Stethoscope className="h-4 w-4" />
                    Assess
                  </button>
                )}
              </div>
            </div>
          )}

          {loadingPatients ? (
            <div className="space-y-3 px-1 mt-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="patient-card p-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="skeleton w-12 h-12 rounded-2xl shrink-0" />
                    <div className="flex-1 space-y-2.5">
                      <div className="skeleton h-4 w-3/4 rounded-lg" />
                      <div className="skeleton h-3 w-1/2 rounded-lg" />
                      <div className="flex gap-2">
                        <div className="skeleton h-5 w-20 rounded-full" />
                        <div className="skeleton h-5 w-16 rounded-full" />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : patients.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-20 h-20 rounded-3xl bg-primary/8 flex items-center justify-center mb-6 ring-1 ring-primary/10">
                <Stethoscope className="h-9 w-9 text-primary/40" />
              </div>
              <p className="text-[17px] font-semibold text-foreground mb-2 tracking-tight">
                Start your patient list
              </p>
              <p className="text-[13px] text-muted-foreground text-center max-w-[260px] mb-8 leading-relaxed">
                Register your first patient to begin AI-powered wound assessments.
              </p>
              <NewPatientDialog
                onCreated={handlePatientCreated}
                trigger={
                  <button
                    type="button"
                    className="flex items-center gap-2.5 px-7 h-13 rounded-2xl
                               bg-primary text-primary-foreground
                               text-[14px] font-semibold
                               shadow-[0_0_20px_rgba(59,130,246,0.2)]
                               active:shadow-[0_0_10px_rgba(59,130,246,0.15)]
                               transition-shadow"
                  >
                    <Plus className="h-5 w-5" />
                    Register Patient
                  </button>
                }
              />
              <div className="mt-12 space-y-4 w-full max-w-[280px]">
                {[
                  { icon: Zap, text: "AI-powered wound analysis", color: "text-blue-400 bg-blue-500/10 ring-blue-500/15" },
                  { icon: Activity, text: "Track healing trajectory", color: "text-emerald-400 bg-emerald-500/10 ring-emerald-500/15" },
                  { icon: Shield, text: "Clinical-grade reporting", color: "text-violet-400 bg-violet-500/10 ring-violet-500/15" },
                ].map(({ icon: Icon, text, color }, i) => (
                  <div key={i} className="flex items-center gap-3.5 animate-slide-up" style={{ animationDelay: `${200 + i * 80}ms` }}>
                    <div className={cn("w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ring-1", color)}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="text-[13px] text-muted-foreground leading-snug">{text}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-4 ring-1 ring-border">
                <Search className="h-6 w-6 text-muted-foreground/30" />
              </div>
              <p className="text-[15px] font-semibold text-foreground mb-1">No results</p>
              <p className="text-[12px] text-muted-foreground text-center max-w-[220px]">
                No patients match &ldquo;{searchQuery}&rdquo;
              </p>
            </div>
          ) : (
            <div className="mt-1">
              {/* Needs Attention section */}
              {attentionPatients.length > 0 && (
                <div className="apple-card overflow-hidden mb-4">
                  <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/30">
                    <div className="w-5 h-5 rounded-md bg-rose-500/15 flex items-center justify-center ring-1 ring-rose-500/20">
                      <AlertTriangle className="h-2.5 w-2.5 text-rose-400" />
                    </div>
                    <h2 className="text-[11px] font-bold text-rose-400/80 uppercase tracking-[0.1em]">
                      Needs Attention
                    </h2>
                    <div className="flex-1" />
                    <span className="text-[11px] font-bold text-rose-400 tabular-nums">
                      {attentionPatients.length}
                    </span>
                  </div>
                  <div className="divide-y divide-border/20">
                    {attentionPatients.map((patient, i) => (
                      <PatientCard key={patient.id} patient={patient} urgent index={i} />
                    ))}
                  </div>
                </div>
              )}

              {/* Other patients */}
              {otherPatients.length > 0 && (
                <div className="apple-card overflow-hidden mb-4">
                  <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/30">
                    <div className="w-5 h-5 rounded-md bg-muted flex items-center justify-center ring-1 ring-border">
                      <Users className="h-2.5 w-2.5 text-muted-foreground" />
                    </div>
                    <h2 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
                      {attentionPatients.length > 0 ? "Monitoring" : "All Patients"}
                    </h2>
                    <div className="flex-1" />
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                      {otherPatients.length}
                    </span>
                  </div>
                  <div className="divide-y divide-border/20">
                    {otherPatients.map((patient, i) => (
                      <PatientCard key={patient.id} patient={patient} index={i + attentionPatients.length} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Mobile: Selected Patient Header (compact, shown on Assess/Report/History)
  // ---------------------------------------------------------------------------

  function MobilePatientHeader() {
    if (!selectedPatient) return null;

    return (
      <div className="shrink-0 bg-[var(--surface-1)] border-b border-border/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="relative shrink-0">
            <div className="w-9 h-9 rounded-xl bg-primary/15 flex items-center justify-center text-[11px] font-bold text-primary ring-1 ring-primary/20">
              {getInitials(selectedPatient.name)}
            </div>
            <span
              className={cn(
                "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--surface-1)]",
                alertDotColor(selectedPatient.latest_alert_level)
              )}
            />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-semibold text-foreground truncate leading-tight">
              {selectedPatient.name}
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {woundLabel(selectedPatient.wound_type, selectedPatient.wound_location)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab("patients")}
            className="text-primary text-[13px] font-medium px-3 py-1.5 -mr-2 min-h-[44px] flex items-center
                       bg-primary/10 rounded-lg ring-1 ring-primary/15 active:bg-primary/20 transition-colors"
          >
            Change
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Mobile: No Patient Selected empty state
  // ---------------------------------------------------------------------------

  function NoPatientSelected({ actionLabel }: { actionLabel: string }) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4 ring-1 ring-border">
          <Users className="h-8 w-8 text-muted-foreground/30" />
        </div>
        <p className="text-sm font-medium text-foreground mb-1">No patient selected</p>
        <p className="text-xs text-muted-foreground text-center mb-5 max-w-[240px]">
          Select a patient from the Patients tab to {actionLabel}.
        </p>
        <button
          type="button"
          onClick={() => setActiveTab("patients")}
          className="flex items-center gap-2 px-5 h-10 rounded-xl
                     bg-primary/15 text-primary text-[13px] font-semibold
                     ring-1 ring-primary/20 active:bg-primary/25 transition-colors"
        >
          <Users className="h-4 w-4" />
          Go to Patients
        </button>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Mobile: Dashboard Tab (assessment + results combined)
  // ---------------------------------------------------------------------------

  function MobileReportTab() {
    return (
      <div className="h-full flex flex-col">
        <MobilePatientHeader />
        {selectedPatient ? (
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {/* Assessment form — collapsible section above the dashboard */}
            {showAssessForm ? (
              <div className="apple-card overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/30">
                  <div className="flex items-center gap-2">
                    <Stethoscope className="h-3.5 w-3.5 text-primary" />
                    <span className="text-[12px] font-semibold text-foreground">New Assessment</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAssessForm(false)}
                    className="text-[12px] text-muted-foreground active:text-foreground transition-colors px-2 py-1 -mr-2"
                  >
                    Cancel
                  </button>
                </div>
                <div className="p-0">
                  <AssessmentPanel
                    patient={selectedPatient}
                    onAnalysisComplete={handleAnalysisComplete}
                  />
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowAssessForm(true)}
                className="w-full flex items-center justify-center gap-2.5 h-12 rounded-2xl
                           bg-primary/15 text-primary text-[14px] font-semibold
                           ring-1 ring-primary/20 active:bg-primary/25 transition-colors"
              >
                <Stethoscope className="h-4 w-4" />
                New Assessment
              </button>
            )}

            {/* Dashboard content — always visible when results exist */}
            {analysisResult && (
              <>
                <ReportPanel
                  result={analysisResult}
                  patientId={selectedPatient.id}
                  patientName={selectedPatient.name}
                  woundType={selectedPatient.wound_type}
                  referringPhysician={selectedPatient.referring_physician}
                  referringPhysicianPhone={selectedPatient.referring_physician_phone}
                  referringPhysicianEmail={selectedPatient.referring_physician_email}
                  referringPhysicianPreferredContact={selectedPatient.referring_physician_preferred_contact}
                />
                <AssessmentHistory
                  patientId={selectedPatient.id}
                  currentAssessmentId={analysisResult.assessment_id}
                  onSelectAssessment={handleSelectHistoryAssessment}
                  refreshKey={trajectoryRefresh}
                />
              </>
            )}

            {/* Empty state when no analysis yet and form is closed */}
            {!analysisResult && !showAssessForm && (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-4 ring-1 ring-border">
                  <FileText className="h-6 w-6 text-muted-foreground/30" />
                </div>
                <p className="text-[14px] font-semibold text-foreground mb-1">No assessments yet</p>
                <p className="text-[12px] text-muted-foreground text-center max-w-[240px] leading-relaxed">
                  Run a first assessment to see the clinical dashboard for this patient.
                </p>
              </div>
            )}
          </div>
        ) : (
          <NoPatientSelected actionLabel="view assessment reports" />
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Mobile: Settings Tab
  // ---------------------------------------------------------------------------

  function MobileSettingsTab() {
    return (
      <div className="h-full overflow-y-auto px-4 py-4">
        <SettingsPanel onSignOut={onSignOut} />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Mobile: Bottom Tab Bar
  // ---------------------------------------------------------------------------

  function MobileTabBar() {
    return (
      <nav
        className="shrink-0 bg-[var(--surface-1)]/95 backdrop-blur-xl border-t border-border/50"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        role="tablist"
        aria-label="Main navigation"
      >
        <div className="flex items-stretch">
          {MOBILE_TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            const showDot = tab.id === "reports" && analysisResult !== null && activeTab !== "reports";

            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id === "reports") setShowAssessForm(false);
                }}
                className={cn(
                  "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 min-h-[50px] transition-all relative",
                  isActive ? "text-primary" : "text-muted-foreground/50"
                )}
              >
                <div className="relative">
                  {isActive && (
                    <span className="absolute -inset-2 rounded-xl bg-primary/10" />
                  )}
                  <Icon className={cn("h-[22px] w-[22px] relative", isActive && "drop-shadow-[0_0_6px_rgba(59,130,246,0.3)]")} strokeWidth={isActive ? 2.2 : 1.6} />
                  {showDot && (
                    <span className="absolute -top-0.5 -right-1.5 h-2.5 w-2.5 rounded-full bg-red-500 border-2 border-[var(--surface-1)]" />
                  )}
                </div>
                <span
                  className={cn(
                    "text-[10px] leading-tight relative",
                    isActive ? "font-bold" : "font-medium"
                  )}
                >
                  {tab.label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header -- dark surface */}
      <header className="shrink-0 bg-[var(--surface-1)] border-b border-border/50">
        <div className="flex items-center justify-between px-4 h-12">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center ring-1 ring-primary/20">
              <Heart className="h-3.5 w-3.5 text-primary" />
            </div>
            <h1 className="text-base font-bold text-foreground leading-tight tracking-tight">
              Wound Monitor
            </h1>
          </div>

          <div className="hidden md:flex items-center gap-3">
            {selectedPatient && (
              <div className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-muted ring-1 ring-border">
                <span className="text-muted-foreground">Patient:</span>
                <span className="font-semibold text-foreground">{selectedPatient.name}</span>
              </div>
            )}
            <Badge
              variant="secondary"
              className="text-xs px-2.5 py-1 gap-1.5 font-normal bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              HAI-DEF Models
            </Badge>
          </div>
        </div>
      </header>

      {/* Error banner */}
      {patientFetchError && !loadingPatients && (
        <div className="shrink-0 px-4 py-2 bg-rose-500/10 border-b border-rose-500/15">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-rose-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{patientFetchError}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchPatients}
              className="shrink-0 gap-1.5 text-xs border-rose-500/20 text-rose-400 hover:bg-rose-500/10"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Desktop Layout (md+) */}
      <div className="hidden md:flex flex-1 min-h-0">
        <aside className="w-[300px] bg-[var(--surface-1)] shrink-0 overflow-hidden border-r border-border/50">
          <PatientList
            patients={patients}
            selectedId={selectedPatient?.id ?? null}
            loading={loadingPatients}
            onSelect={handleSelectPatient}
            onPatientCreated={handlePatientCreated}
          />
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto p-5 space-y-4">
          {selectedPatient ? (
            <>
              <AssessmentPanel
                patient={selectedPatient}
                onAnalysisComplete={handleAnalysisComplete}
              />
              {analysisResult && (
                <ReportPanel
                  result={analysisResult}
                  patientId={selectedPatient.id}
                  patientName={selectedPatient.name}
                  woundType={selectedPatient.wound_type}
                  referringPhysician={selectedPatient.referring_physician}
                  referringPhysicianPhone={selectedPatient.referring_physician_phone}
                  referringPhysicianEmail={selectedPatient.referring_physician_email}
                  referringPhysicianPreferredContact={selectedPatient.referring_physician_preferred_contact}
                />
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
              <div className="w-16 h-16 rounded-2xl bg-primary/8 flex items-center justify-center mb-4 ring-1 ring-primary/10">
                <Stethoscope className="h-8 w-8 text-primary/40" />
              </div>
              <p className="text-sm text-center max-w-xs leading-relaxed">
                Select a patient from the sidebar or register a new one to begin wound assessment.
              </p>
            </div>
          )}
        </main>

        <aside className="w-[360px] bg-[var(--surface-1)] shrink-0 overflow-y-auto p-4 space-y-4 border-l border-border/50">
          {selectedPatient ? (
            <>
              <TimelineChart
                patientId={selectedPatient.id}
                refreshKey={trajectoryRefresh}
              />
              {analysisResult && (
                <AssessmentHistory
                  patientId={selectedPatient.id}
                  currentAssessmentId={analysisResult.assessment_id}
                  onSelectAssessment={handleSelectHistoryAssessment}
                  refreshKey={trajectoryRefresh}
                />
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center mb-3 ring-1 ring-border">
                <Activity className="h-7 w-7 opacity-30" />
              </div>
              <p className="text-sm font-medium">Trajectory</p>
              <p className="text-xs mt-1 text-muted-foreground/50">Select a patient to view history.</p>
            </div>
          )}
        </aside>
      </div>

      {/* Mobile Layout -- tab-based navigation */}
      <div className="flex md:hidden flex-1 min-h-0 flex-col">
        {/* Tab content area */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeTab === "patients" && <MobilePatientsTab />}
          {activeTab === "reports" && <MobileReportTab />}
          {activeTab === "settings" && <MobileSettingsTab />}
        </div>

        {/* Bottom tab bar */}
        <MobileTabBar />
      </div>
    </div>
  );
}
