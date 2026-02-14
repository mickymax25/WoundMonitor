"use client";

import React from "react";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  FileText,
} from "lucide-react";
import { cn, alertDotColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
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
      return <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />;
    case "deteriorating":
      return <TrendingDown className="h-3.5 w-3.5 text-rose-500" />;
    case "stable":
      return <Minus className="h-3.5 w-3.5 text-amber-500" />;
    default:
      return <Activity className="h-3.5 w-3.5 text-slate-500" />;
  }
}

function trajectoryBadgeVariant(
  trajectory: string | null
): "success" | "warning" | "danger" | "secondary" {
  switch (trajectory) {
    case "improving":
      return "success";
    case "stable":
      return "warning";
    case "deteriorating":
      return "danger";
    default:
      return "secondary";
  }
}

function woundTypeLabel(type: string | null): string {
  if (!type) return "";
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function PatientList({
  patients,
  selectedId,
  loading,
  onSelect,
  onPatientCreated,
}: PatientListProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
            Patients
          </h2>
          <span className="text-xs text-muted-foreground">
            {patients.length}
          </span>
        </div>
        <NewPatientDialog onCreated={onPatientCreated} />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-20 rounded-lg" />
            ))}
          </div>
        ) : patients.length === 0 ? (
          <div className="p-6 text-center text-muted-foreground text-sm">
            <FileText className="h-8 w-8 mx-auto mb-2 opacity-40" />
            No patients registered yet.
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {patients.map((patient) => (
              <button
                key={patient.id}
                type="button"
                onClick={() => onSelect(patient)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors",
                  "hover:bg-accent/50",
                  selectedId === patient.id
                    ? "bg-accent border border-primary/30"
                    : "border border-transparent"
                )}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={cn(
                      "mt-1.5 h-2.5 w-2.5 rounded-full shrink-0",
                      alertDotColor(patient.latest_alert_level)
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {patient.name}
                    </p>
                    {patient.wound_type && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {woundTypeLabel(patient.wound_type)}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5">
                      {patient.latest_trajectory && (
                        <Badge
                          variant={trajectoryBadgeVariant(
                            patient.latest_trajectory
                          )}
                          className="text-[10px] px-1.5 py-0 h-5 gap-1"
                        >
                          <TrajectoryIcon
                            trajectory={patient.latest_trajectory}
                          />
                          {patient.latest_trajectory}
                        </Badge>
                      )}
                      <span className="text-[10px] text-muted-foreground">
                        {patient.assessment_count} assessment
                        {patient.assessment_count !== 1 ? "s" : ""}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
