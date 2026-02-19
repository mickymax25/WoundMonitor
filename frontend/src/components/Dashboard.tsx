"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  Stethoscope,
  Activity,
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
  ShieldAlert,
  Zap,
  Clock,
  Settings2,
  Bot,
  Link2,
  ImagePlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { NewPatientDialog } from "@/components/NewPatientDialog";
import { AssessmentPanel } from "@/components/AssessmentPanel";
import { TimelineChart } from "@/components/TimelineChart";
import { ReportPanel } from "@/components/ReportPanel";
import { AssessmentHistory } from "@/components/AssessmentHistory";
import { PhotoTimeline } from "@/components/PhotoTimeline";
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
            healing_comment: latest.healing_comment ?? null,
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
    setSelectedPatient(null);
    setAnalysisResult(null);
    setShowAssessForm(false);
    setActiveTab("patients");
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
            healing_comment: latest.healing_comment ?? null,
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
        healing_comment: a.healing_comment ?? null,
      });
    },
    []
  );

  // Avatar gradient on dark surface (shared by patient cards + header)
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

  // ---------------------------------------------------------------------------
  // Share Patient Link (for patient self-reporting)
  // ---------------------------------------------------------------------------

  function SharePatientLink({ patient }: { patient: PatientResponse }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(() => {
      const link = `${window.location.origin}/p/${patient.patient_token}`;
      navigator.clipboard.writeText(link).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }, [patient.patient_token]);

    if (!patient.patient_token) return null;

    return (
      <button
        type="button"
        onClick={handleCopy}
        className={cn(
          "w-full flex items-center gap-3 px-4 py-3 rounded-2xl transition-all active:scale-[0.98]",
          copied
            ? "bg-emerald-500/15 ring-1 ring-emerald-500/25"
            : "bg-violet-500/10 ring-1 ring-violet-500/20 hover:bg-violet-500/15"
        )}
      >
        <div className={cn(
          "w-9 h-9 rounded-xl flex items-center justify-center shrink-0",
          copied ? "bg-emerald-500/20" : "bg-violet-500/20"
        )}>
          <Link2 className={cn("h-4 w-4", copied ? "text-emerald-400" : "text-violet-400")} />
        </div>
        <div className="flex-1 text-left min-w-0">
          <p className={cn("text-[13px] font-semibold", copied ? "text-emerald-400" : "text-violet-300")}>
            {copied ? "Link copied!" : "Share photo upload link"}
          </p>
          <p className="text-[11px] text-muted-foreground truncate">
            {copied ? "Send it to the patient via SMS or WhatsApp" : "Patient can send wound photos between visits"}
          </p>
        </div>
        <ChevronRight className={cn("h-4 w-4 shrink-0", copied ? "text-emerald-400/50" : "text-violet-400/50")} />
      </button>
    );
  }

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

    let userName = "";
    try {
      const raw = localStorage.getItem("wm_auth");
      if (raw) {
        const auth = JSON.parse(raw);
        userName = (auth.name || "").split(",")[0].split(" ")[0];
      }
    } catch { /* ignore */ }
    const greeting = userName ? `Hello ${userName}` : "Hello";
    const dateStr = new Date().toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });

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
                  {patient.patient_reported_count > 0 && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full ring-1 ring-blue-500/15 animate-pulse">
                      <ImagePlus className="h-2.5 w-2.5" />
                      {patient.patient_reported_count} new
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
    const [showShareLink, setShowShareLink] = useState(false);
    const [linkCopied, setLinkCopied] = useState(false);

    if (!selectedPatient) return null;

    const isUrgent = selectedPatient.latest_alert_level === "red" || selectedPatient.latest_alert_level === "orange";
    const alertColor = (() => {
      switch (selectedPatient.latest_alert_level) {
        case "red": return "bg-rose-500";
        case "orange": return "bg-orange-400";
        case "yellow": return "bg-amber-400";
        case "green": return "bg-emerald-500";
        default: return "bg-slate-500";
      }
    })();

    const meta: string[] = [];
    if (selectedPatient.age) meta.push(`${selectedPatient.age}y`);
    if (selectedPatient.assessment_count > 0) meta.push(`${selectedPatient.assessment_count} visit${selectedPatient.assessment_count > 1 ? "s" : ""}`);

    const patientLink = typeof window !== "undefined"
      ? `${window.location.origin}/p/${selectedPatient.patient_token}`
      : "";

    return (
      <>
      <div className="shrink-0 px-4 pt-3 pb-1">
        <div className="apple-card flex items-center gap-3 px-3.5 py-3">
          {/* Avatar */}
          <div className="relative shrink-0">
            <div
              className={cn(
                "w-11 h-11 rounded-[14px] flex items-center justify-center text-[13px] font-bold tracking-wide",
                avatarGradient(selectedPatient, isUrgent)
              )}
            >
              {getInitials(selectedPatient.name)}
            </div>
            <span
              className={cn(
                "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--bg-base)]",
                alertColor
              )}
            />
          </div>

          {/* Name + wound + meta */}
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-semibold text-foreground truncate leading-tight">
              {selectedPatient.name}
            </p>
            <p className="text-[11px] text-muted-foreground truncate mt-[2px]">
              {woundLabel(selectedPatient.wound_type, selectedPatient.wound_location)}
              {meta.length > 0 && <span className="text-muted-foreground/40"> · {meta.join(" · ")}</span>}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => { setShowShareLink(true); setLinkCopied(false); }}
              className="h-8 w-8 flex items-center justify-center rounded-lg
                         text-violet-400 text-[11px]
                         bg-violet-500/10 ring-1 ring-violet-500/15 active:bg-violet-500/20 transition-colors"
              title="Patient upload link"
            >
              <Link2 className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setShowAssessForm(true)}
              className="h-8 px-3 flex items-center gap-1.5 rounded-lg
                         text-primary text-[11px] font-semibold
                         bg-primary/10 ring-1 ring-primary/15 active:bg-primary/20 transition-colors"
            >
              <Stethoscope className="h-3 w-3" />
              Assess
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("patients")}
              className="h-8 px-2.5 flex items-center rounded-lg
                         text-muted-foreground text-[11px] font-medium
                         bg-white/[0.04] ring-1 ring-white/[0.06] active:bg-white/[0.08] transition-colors"
            >
              Change
            </button>
          </div>
        </div>
      </div>

      {/* Share link overlay */}
      {showShareLink && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-6"
          onClick={() => setShowShareLink(false)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-sm rounded-2xl border border-white/[0.08] p-5 shadow-2xl space-y-4"
            style={{
              background: "linear-gradient(180deg, hsl(226 30% 19%) 0%, hsl(228 32% 14%) 100%)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <p className="text-[14px] font-semibold text-violet-300 mb-1">Photo upload link</p>
              <p className="text-[12px] text-muted-foreground leading-relaxed">
                Share this link with <span className="text-foreground font-medium">{selectedPatient.name}</span> so they can send wound photos between visits.
              </p>
            </div>

            <div className="flex items-center gap-2 bg-black/25 rounded-xl px-3 py-2.5 ring-1 ring-white/[0.06]">
              <p className="flex-1 text-[11px] text-foreground/70 font-mono truncate">
                {patientLink}
              </p>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(patientLink).then(() => {
                    setLinkCopied(true);
                    setTimeout(() => setLinkCopied(false), 2500);
                  });
                }}
                className={cn(
                  "shrink-0 text-[11px] font-bold px-3 py-1.5 rounded-lg transition-colors",
                  linkCopied
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-violet-500/20 text-violet-300 active:bg-violet-500/30"
                )}
              >
                {linkCopied ? "Copied!" : "Copy"}
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowShareLink(false)}
              className="w-full h-11 rounded-xl bg-white/[0.06] ring-1 ring-white/[0.08] text-foreground text-[13px] font-semibold
                         active:bg-white/[0.10] transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}
      </>
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
            {showAssessForm && (
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
                  renderBeforeSummary={
                    <PhotoTimeline
                      patientId={selectedPatient.id}
                      refreshKey={trajectoryRefresh}
                      onSelectAssessment={handleSelectHistoryAssessment}
                    />
                  }
                />
                <AssessmentHistory
                  patientId={selectedPatient.id}
                  currentAssessmentId={analysisResult.assessment_id}
                  onSelectAssessment={handleSelectHistoryAssessment}
                  refreshKey={trajectoryRefresh}
                />

                {/* AI Disclaimer */}
                <div className="flex items-start gap-2.5 px-2 py-3">
                  <Bot className="h-4 w-4 text-muted-foreground/40 mt-0.5 shrink-0" />
                  <p className="text-xs text-muted-foreground/50 leading-relaxed">
                    AI-generated report — Wound Monitor (MedGemma + MedSigLIP + MedASR). For clinical decision support only. Does not constitute a diagnosis.
                  </p>
                </div>
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
          <div className="flex items-center">
            <img
              src="/LogoWM_V2.png"
              alt="Wound Monitor"
              height={32}
              width={140}
              className="h-8 w-auto"
            />
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
              <PhotoTimeline
                patientId={selectedPatient.id}
                refreshKey={trajectoryRefresh}
                onSelectAssessment={handleSelectHistoryAssessment}
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
          {activeTab === "patients" && <div key="tab-patients" className="animate-tab-enter h-full"><MobilePatientsTab /></div>}
          {activeTab === "reports" && <div key="tab-reports" className="animate-tab-enter h-full"><MobileReportTab /></div>}
          {activeTab === "settings" && <div key="tab-settings" className="animate-tab-enter h-full"><MobileSettingsTab /></div>}
        </div>

        {/* Bottom tab bar */}
        <MobileTabBar />
      </div>
    </div>
  );
}
