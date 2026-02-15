"use client";

import React, { useState, useCallback } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { createPatient } from "@/lib/api";
import { WOUND_TYPES, WOUND_LOCATIONS } from "@/lib/types";
import type { PatientResponse } from "@/lib/types";

const COMORBIDITY_OPTIONS = [
  { value: "diabetes", label: "Diabetes" },
  { value: "hypertension", label: "Hypertension" },
  { value: "peripheral_neuropathy", label: "Peripheral Neuropathy" },
  { value: "venous_insufficiency", label: "Venous Insufficiency" },
  { value: "anemia", label: "Anemia" },
  { value: "leprosy", label: "Leprosy" },
  { value: "immunosuppression", label: "Immunosuppression" },
  { value: "obesity", label: "Obesity" },
] as const;

interface NewPatientDialogProps {
  onCreated: (patient: PatientResponse) => void;
}

export function NewPatientDialog({ onCreated }: NewPatientDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [woundType, setWoundType] = useState("");
  const [woundLocation, setWoundLocation] = useState("");
  const [comorbidities, setComorbidities] = useState<string[]>([]);

  const toggleComorbidity = useCallback((value: string) => {
    setComorbidities((prev) =>
      prev.includes(value)
        ? prev.filter((c) => c !== value)
        : [...prev, value]
    );
  }, []);

  const resetForm = useCallback(() => {
    setName("");
    setAge("");
    setWoundType("");
    setWoundLocation("");
    setComorbidities([]);
    setError(null);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) {
        setError("Patient name is required.");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const patient = await createPatient({
          name: name.trim(),
          age: age ? parseInt(age, 10) : null,
          wound_type: woundType || null,
          wound_location: woundLocation || null,
          comorbidities,
        });
        onCreated(patient);
        setOpen(false);
        resetForm();
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to create patient."
        );
      } finally {
        setLoading(false);
      }
    },
    [name, age, woundType, woundLocation, comorbidities, onCreated, resetForm]
  );

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm(); }}>
      <DialogTrigger asChild>
        <Button size="sm" className="w-full gap-2">
          <Plus className="h-4 w-4" />
          New Patient
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register New Patient</DialogTitle>
          <DialogDescription>
            Add a new patient to begin wound assessment tracking.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="patient-name">
              Name <span className="text-red-400">*</span>
            </Label>
            <Input
              id="patient-name"
              placeholder="Patient full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="patient-age">Age</Label>
            <Input
              id="patient-age"
              type="number"
              placeholder="Optional"
              min={0}
              max={150}
              value={age}
              onChange={(e) => setAge(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="wound-type">Wound Type</Label>
            <Select value={woundType} onValueChange={setWoundType}>
              <SelectTrigger id="wound-type">
                <SelectValue placeholder="Select wound type" />
              </SelectTrigger>
              <SelectContent>
                {WOUND_TYPES.map((wt) => (
                  <SelectItem key={wt.value} value={wt.value}>
                    {wt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="wound-location">Wound Location</Label>
            <Select
              value={woundLocation}
              onValueChange={setWoundLocation}
            >
              <SelectTrigger id="wound-location">
                <SelectValue placeholder="Select wound location" />
              </SelectTrigger>
              <SelectContent>
                {WOUND_LOCATIONS.map((wl) => (
                  <SelectItem key={wl.value} value={wl.value}>
                    {wl.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Comorbidities</Label>
            <div className="flex flex-wrap gap-2">
              {COMORBIDITY_OPTIONS.map((opt) => {
                const selected = comorbidities.includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleComorbidity(opt.value)}
                    className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                      selected
                        ? "bg-primary/20 border-primary text-primary"
                        : "bg-transparent border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-400" role="alert">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create Patient"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
