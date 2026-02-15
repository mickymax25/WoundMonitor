"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  Stethoscope,
  Activity,
  FileText,
  Heart,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PatientList } from "@/components/PatientList";
import { AssessmentPanel } from "@/components/AssessmentPanel";
import { TimelineChart } from "@/components/TimelineChart";
import { ReportPanel } from "@/components/ReportPanel";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { listPatients } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PatientResponse, AnalysisResult, MobileTab } from "@/lib/types";

export default function DashboardPage() {
  const [patients, setPatients] = useState<PatientResponse[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientFetchError, setPatientFetchError] = useState<string | null>(null);
  const [selectedPatient, setSelectedPatient] =
    useState<PatientResponse | null>(null);
  const [analysisResult, setAnalysisResult] =
    useState<AnalysisResult | null>(null);
  const [trajectoryRefresh, setTrajectoryRefresh] = useState(0);
  const [mobileTab, setMobileTab] = useState<MobileTab>("patients");

  const fetchPatients = useCallback(async () => {
    setLoadingPatients(true);
    setPatientFetchError(null);
    try {
      const data = await listPatients();
      setPatients(data);
    } catch (err) {
      setPatientFetchError(
        err instanceof Error ? err.message : "Failed to load patients."
      );
    } finally {
      setLoadingPatients(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const handleSelectPatient = useCallback((patient: PatientResponse) => {
    setSelectedPatient(patient);
    setAnalysisResult(null);
    setTrajectoryRefresh((r) => r + 1);
    setMobileTab("assessment");
  }, []);

  const handlePatientCreated = useCallback(
    (patient: PatientResponse) => {
      setPatients((prev) => [patient, ...prev]);
      setSelectedPatient(patient);
      setAnalysisResult(null);
      setMobileTab("assessment");
    },
    []
  );

  const handleAnalysisComplete = useCallback(
    (result: AnalysisResult) => {
      setAnalysisResult(result);
      setTrajectoryRefresh((r) => r + 1);
      fetchPatients();
    },
    [fetchPatients]
  );

  const EmptyCenter = () => (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
      <div className="w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6 border border-primary/20">
        <Stethoscope className="h-10 w-10 text-primary/60" />
      </div>
      <h3 className="text-xl font-semibold text-foreground mb-2">
        WoundChrono
      </h3>
      <p className="text-sm text-center max-w-xs leading-relaxed">
        Select a patient from the sidebar or register a new one to begin
        wound assessment.
      </p>
    </div>
  );

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="shrink-0 border-b border-border bg-card/80 backdrop-blur-md">
        <div className="flex items-center justify-between px-5 h-16">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/15 flex items-center justify-center border border-primary/20">
              <Heart className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-base font-bold text-foreground leading-tight tracking-tight">
                WoundChrono
              </h1>
              <p className="text-[10px] text-muted-foreground leading-tight">
                AI-Powered Wound Assessment
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-4">
            {selectedPatient && (
              <div className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-md bg-accent/50 border border-border">
                <span className="text-muted-foreground text-xs">Patient:</span>
                <span className="font-medium text-foreground text-xs">
                  {selectedPatient.name}
                </span>
              </div>
            )}
            <Badge variant="secondary" className="text-[10px] px-2.5 py-1 gap-1.5 font-normal border border-border bg-accent/30">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              MedGemma + MedSigLIP + MedASR
            </Badge>
          </div>
        </div>
      </header>

      {/* Patient fetch error banner */}
      {patientFetchError && !loadingPatients && (
        <div className="shrink-0 px-4 py-2 bg-destructive/10 border-b border-destructive/30">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{patientFetchError}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchPatients}
              className="shrink-0 gap-1.5 text-xs border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Desktop Layout (md+) */}
      <div className="hidden md:flex flex-1 min-h-0">
        {/* Left Sidebar - Patient List */}
        <aside className="w-[300px] border-r border-border bg-card/40 shrink-0 overflow-hidden">
          <PatientList
            patients={patients}
            selectedId={selectedPatient?.id ?? null}
            loading={loadingPatients}
            onSelect={handleSelectPatient}
            onPatientCreated={handlePatientCreated}
          />
        </aside>

        {/* Center Panel */}
        <main className="flex-1 min-w-0 overflow-y-auto p-6 space-y-5">
          {selectedPatient ? (
            <>
              <AssessmentPanel
                patient={selectedPatient}
                onAnalysisComplete={handleAnalysisComplete}
              />
              <ReportPanel
                result={analysisResult}
                patientName={selectedPatient.name}
                woundType={selectedPatient.wound_type}
              />
            </>
          ) : (
            <EmptyCenter />
          )}
        </main>

        {/* Right Sidebar - Timeline */}
        <aside className="w-[380px] border-l border-border bg-card/40 shrink-0 overflow-y-auto p-5">
          {selectedPatient ? (
            <TimelineChart
              patientId={selectedPatient.id}
              refreshKey={trajectoryRefresh}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <div className="w-14 h-14 rounded-xl bg-accent/50 flex items-center justify-center mb-3 border border-border">
                <Activity className="h-7 w-7 opacity-40" />
              </div>
              <p className="text-sm font-medium">Trajectory Chart</p>
              <p className="text-xs mt-1 text-muted-foreground/60">
                Select a patient to view history.
              </p>
            </div>
          )}
        </aside>
      </div>

      {/* Mobile Layout */}
      <div className="flex md:hidden flex-1 min-h-0 flex-col">
        <Tabs
          value={mobileTab}
          onValueChange={(v) => setMobileTab(v as MobileTab)}
          className="flex flex-col flex-1 min-h-0"
        >
          <TabsList className="w-full rounded-none border-b border-border h-12 bg-card/60 shrink-0">
            <TabsTrigger value="patients" className="flex-1 gap-1.5 text-xs">
              <Users className="h-3.5 w-3.5" />
              Patients
            </TabsTrigger>
            <TabsTrigger
              value="assessment"
              className={cn(
                "flex-1 gap-1.5 text-xs",
                !selectedPatient && "opacity-50"
              )}
              disabled={!selectedPatient}
            >
              <Stethoscope className="h-3.5 w-3.5" />
              Assess
            </TabsTrigger>
            <TabsTrigger
              value="timeline"
              className={cn(
                "flex-1 gap-1.5 text-xs",
                !selectedPatient && "opacity-50"
              )}
              disabled={!selectedPatient}
            >
              <Activity className="h-3.5 w-3.5" />
              Timeline
            </TabsTrigger>
            <TabsTrigger
              value="report"
              className={cn(
                "flex-1 gap-1.5 text-xs",
                !analysisResult && "opacity-50"
              )}
              disabled={!analysisResult}
            >
              <FileText className="h-3.5 w-3.5" />
              Report
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="patients"
            className="flex-1 min-h-0 overflow-y-auto mt-0"
          >
            <PatientList
              patients={patients}
              selectedId={selectedPatient?.id ?? null}
              loading={loadingPatients}
              onSelect={handleSelectPatient}
              onPatientCreated={handlePatientCreated}
            />
          </TabsContent>

          <TabsContent
            value="assessment"
            className="flex-1 min-h-0 overflow-y-auto p-4 mt-0"
          >
            {selectedPatient ? (
              <AssessmentPanel
                patient={selectedPatient}
                onAnalysisComplete={handleAnalysisComplete}
              />
            ) : (
              <EmptyCenter />
            )}
          </TabsContent>

          <TabsContent
            value="timeline"
            className="flex-1 min-h-0 overflow-y-auto p-4 mt-0"
          >
            {selectedPatient ? (
              <TimelineChart
                patientId={selectedPatient.id}
                refreshKey={trajectoryRefresh}
              />
            ) : (
              <div className="text-center py-12 text-muted-foreground text-sm">
                Select a patient first.
              </div>
            )}
          </TabsContent>

          <TabsContent
            value="report"
            className="flex-1 min-h-0 overflow-y-auto p-4 mt-0"
          >
            <ReportPanel
              result={analysisResult}
              patientName={selectedPatient?.name ?? null}
              woundType={selectedPatient?.wound_type ?? null}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
