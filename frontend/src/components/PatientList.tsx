"use client";

import React, { useMemo } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  FileText,
  MapPin,
} from "lucide-react";
import { cn, alertDotColor, formatDate } from "@/lib/utils";
import { NewPatientDialog } from "@/components/NewPatientDialog";
import type { PatientResponse } from "@/lib/types";

interface PatientListProps {
  patients: PatientResponse[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (patient: PatientResponse) => void;
  onPatientCreated: (patient: PatientResponse) => void;
}

function TrajectoryIcon({ trajectory }: { trajectory: string | null }) {
  switch (trajectory) {
    case "improving":
      return <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />;
    case "deteriorating":
      return <TrendingDown className="h-3.5 w-3.5 text-rose-400" />;
    case "stable":
      return <Minus className="h-3.5 w-3.5 text-sky-400" />;
    default:
      return <Activity className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function woundTypeLabel(type: string | null): string {
  if (!type) return "";
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function woundLocationLabel(location: string | null): string {
  if (!location) return "";
  return location
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function avatarBgColor(alertLevel: string | null): string {
  switch (alertLevel) {
    case "red":
      return "bg-rose-500/15 text-rose-400 border-rose-500/20";
    case "orange":
      return "bg-orange-500/15 text-orange-400 border-orange-500/20";
    case "yellow":
      return "bg-sky-500/15 text-sky-400 border-sky-500/20";
    case "green":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

function trajectoryLabel(trajectory: string | null): string {
  switch (trajectory) {
    case "improving":
      return "Improving";
    case "stable":
      return "Stable";
    case "deteriorating":
      return "Worsening";
    case "baseline":
      return "Baseline";
    default:
      return "";
  }
}

function trajectoryTextColor(trajectory: string | null): string {
  switch (trajectory) {
    case "improving":
      return "text-emerald-400";
    case "stable":
      return "text-sky-400";
    case "deteriorating":
      return "text-rose-400";
    default:
      return "text-muted-foreground";
  }
}

export function PatientList({
  patients,
  selectedId,
  loading,
  onSelect,
  onPatientCreated,
}: PatientListProps) {
  const sortedPatients = useMemo(() => {
    return [...patients].sort((a, b) => {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [patients]);

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
            Patients
          </h2>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full border border-border">
            {patients.length}
          </span>
        </div>
        <NewPatientDialog onCreated={onPatientCreated} />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-3 p-3">
                <div className="skeleton w-10 h-10 rounded-full shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3.5 w-3/4 rounded" />
                  <div className="skeleton h-2.5 w-1/2 rounded" />
                  <div className="skeleton h-2.5 w-1/3 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : patients.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mx-auto mb-3 border border-border">
              <FileText className="h-6 w-6 opacity-40" />
            </div>
            <p className="text-sm font-medium mb-1">No patients yet</p>
            <p className="text-xs text-muted-foreground/60">
              Register a patient to begin.
            </p>
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {sortedPatients.map((patient) => {
              const isSelected = selectedId === patient.id;
              return (
                <button
                  key={patient.id}
                  type="button"
                  onClick={() => onSelect(patient)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg transition-all duration-150",
                    "hover:bg-muted/50",
                    isSelected
                      ? "bg-primary/10 border-l-2 border-l-primary border border-primary/20"
                      : "border border-transparent"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold shrink-0 border",
                        avatarBgColor(patient.latest_alert_level)
                      )}
                    >
                      {getInitials(patient.name)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-foreground truncate">
                          {patient.name}
                        </p>
                        <span
                          className={cn(
                            "h-2 w-2 rounded-full shrink-0",
                            alertDotColor(patient.latest_alert_level)
                          )}
                        />
                      </div>

                      <div className="flex items-center gap-2 mt-0.5">
                        {patient.wound_type && (
                          <span className="text-xs text-muted-foreground">
                            {woundTypeLabel(patient.wound_type)}
                          </span>
                        )}
                        {patient.wound_type && patient.wound_location && (
                          <span className="text-muted-foreground/40 text-xs">|</span>
                        )}
                        {patient.wound_location && (
                          <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                            <MapPin className="h-2.5 w-2.5" />
                            {woundLocationLabel(patient.wound_location)}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 mt-2">
                        {patient.latest_trajectory && (
                          <span
                            className={cn(
                              "flex items-center gap-1 text-xs font-medium",
                              trajectoryTextColor(patient.latest_trajectory)
                            )}
                          >
                            <TrajectoryIcon trajectory={patient.latest_trajectory} />
                            {trajectoryLabel(patient.latest_trajectory)}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {patient.assessment_count} visit
                          {patient.assessment_count !== 1 ? "s" : ""}
                        </span>
                        {isSelected && patient.created_at && (
                          <span className="text-xs text-muted-foreground ml-auto">
                            {formatDate(patient.created_at)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
