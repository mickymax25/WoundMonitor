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

  const resetForm = useCallback(() => {
    setName("");
    setAge("");
    setWoundType("");
    setWoundLocation("");
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
          comorbidities: [],
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
    [name, age, woundType, woundLocation, onCreated, resetForm]
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
