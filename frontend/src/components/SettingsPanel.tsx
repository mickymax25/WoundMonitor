"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  User,
  Building2,
  Briefcase,
  Save,
  Check,
  Plus,
  Trash2,
  X,
  Stethoscope,
  Phone,
  Info,
  ShieldAlert,
  Heart,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NurseProfile {
  name: string;
  role: string;
  facility: string;
}

interface Physician {
  id: string;
  name: string;
  specialty: string;
  contact: string;
}

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------

const PROFILE_KEY = "wc_nurse_profile";
const PHYSICIANS_KEY = "wc_physicians";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateId(): string {
  return `ph_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const DEFAULT_PROFILE: NurseProfile = {
  name: "Sarah Mitchell, RN",
  role: "Wound Care Nurse",
  facility: "St. Mary's Medical Center",
};

function loadProfile(): NurseProfile {
  if (typeof window === "undefined") return { ...DEFAULT_PROFILE };
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<NurseProfile>;
      return {
        name: parsed.name ?? DEFAULT_PROFILE.name,
        role: parsed.role ?? DEFAULT_PROFILE.role,
        facility: parsed.facility ?? DEFAULT_PROFILE.facility,
      };
    }
  } catch {
    // Corrupted data -- fall through to default
  }
  return { ...DEFAULT_PROFILE };
}

const DEFAULT_PHYSICIANS: Physician[] = [
  {
    id: "ph_default_1",
    name: "Dr. James Chen",
    specialty: "Vascular Surgery",
    contact: "j.chen@stmarys.med",
  },
  {
    id: "ph_default_2",
    name: "Dr. Elena Rodriguez",
    specialty: "Wound Care / Dermatology",
    contact: "e.rodriguez@stmarys.med",
  },
];

function loadPhysicians(): Physician[] {
  if (typeof window === "undefined") return [...DEFAULT_PHYSICIANS];
  try {
    const raw = localStorage.getItem(PHYSICIANS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as Physician[];
    }
  } catch {
    // Corrupted data
  }
  return [...DEFAULT_PHYSICIANS];
}

function saveProfileToStorage(profile: NurseProfile): void {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

function savePhysiciansToStorage(physicians: Physician[]): void {
  localStorage.setItem(PHYSICIANS_KEY, JSON.stringify(physicians));
}

// ---------------------------------------------------------------------------
// Section: Nurse Profile
// ---------------------------------------------------------------------------

function NurseProfileSection() {
  const [profile, setProfile] = useState<NurseProfile>({ ...DEFAULT_PROFILE });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setProfile(loadProfile());
  }, []);

  const handleSave = useCallback(() => {
    saveProfileToStorage(profile);
    setSaved(true);
    const timeout = setTimeout(() => setSaved(false), 2000);
    return () => clearTimeout(timeout);
  }, [profile]);

  const updateField = useCallback(
    (field: keyof NurseProfile, value: string) => {
      setSaved(false);
      setProfile((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  return (
    <div className="apple-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/30">
        <div className="w-5 h-5 rounded-md bg-primary/15 flex items-center justify-center ring-1 ring-primary/20">
          <User className="h-2.5 w-2.5 text-primary" />
        </div>
        <h2 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
          Nurse Profile
        </h2>
      </div>

      <div className="p-4 space-y-4">
        {/* Name */}
        <div className="space-y-1.5">
          <label
            htmlFor="settings-nurse-name"
            className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
          >
            Name
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
            <input
              id="settings-nurse-name"
              type="text"
              placeholder="Your full name"
              value={profile.name}
              onChange={(e) => updateField("name", e.target.value)}
              className={cn(
                "w-full h-11 pl-10 pr-4 text-[13px] text-foreground rounded-xl",
                "bg-[var(--surface-2)] border border-border/30",
                "placeholder:text-muted-foreground/40",
                "focus:outline-none focus:ring-1 focus:ring-primary/30"
              )}
            />
          </div>
        </div>

        {/* Role */}
        <div className="space-y-1.5">
          <label
            htmlFor="settings-nurse-role"
            className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
          >
            Role
          </label>
          <div className="relative">
            <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
            <input
              id="settings-nurse-role"
              type="text"
              placeholder="Wound Care Nurse"
              value={profile.role}
              onChange={(e) => updateField("role", e.target.value)}
              className={cn(
                "w-full h-11 pl-10 pr-4 text-[13px] text-foreground rounded-xl",
                "bg-[var(--surface-2)] border border-border/30",
                "placeholder:text-muted-foreground/40",
                "focus:outline-none focus:ring-1 focus:ring-primary/30"
              )}
            />
          </div>
        </div>

        {/* Facility */}
        <div className="space-y-1.5">
          <label
            htmlFor="settings-nurse-facility"
            className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
          >
            Facility
          </label>
          <div className="relative">
            <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
            <input
              id="settings-nurse-facility"
              type="text"
              placeholder="Hospital or clinic name"
              value={profile.facility}
              onChange={(e) => updateField("facility", e.target.value)}
              className={cn(
                "w-full h-11 pl-10 pr-4 text-[13px] text-foreground rounded-xl",
                "bg-[var(--surface-2)] border border-border/30",
                "placeholder:text-muted-foreground/40",
                "focus:outline-none focus:ring-1 focus:ring-primary/30"
              )}
            />
          </div>
        </div>

        {/* Save */}
        <button
          type="button"
          onClick={handleSave}
          className={cn(
            "w-full flex items-center justify-center gap-2 min-h-[44px] rounded-xl",
            "text-[13px] font-semibold transition-all",
            saved
              ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/20"
              : "bg-primary/15 text-primary ring-1 ring-primary/20 active:bg-primary/25"
          )}
        >
          {saved ? (
            <>
              <Check className="h-4 w-4" />
              Saved
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              Save Profile
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Referring Physicians
// ---------------------------------------------------------------------------

function PhysiciansSection() {
  const [physicians, setPhysicians] = useState<Physician[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);

  // Form fields
  const [formName, setFormName] = useState("");
  const [formSpecialty, setFormSpecialty] = useState("");
  const [formContact, setFormContact] = useState("");

  useEffect(() => {
    setPhysicians(loadPhysicians());
  }, []);

  const persist = useCallback((next: Physician[]) => {
    setPhysicians(next);
    savePhysiciansToStorage(next);
  }, []);

  const resetForm = useCallback(() => {
    setFormName("");
    setFormSpecialty("");
    setFormContact("");
    setShowForm(false);
    setEditId(null);
  }, []);

  const handleAdd = useCallback(() => {
    resetForm();
    setShowForm(true);
  }, [resetForm]);

  const handleEdit = useCallback((physician: Physician) => {
    setFormName(physician.name);
    setFormSpecialty(physician.specialty);
    setFormContact(physician.contact);
    setEditId(physician.id);
    setShowForm(true);
  }, []);

  const handleSave = useCallback(() => {
    const trimmedName = formName.trim();
    if (!trimmedName) return;

    if (editId) {
      // Update existing
      const next = physicians.map((p) =>
        p.id === editId
          ? {
              ...p,
              name: trimmedName,
              specialty: formSpecialty.trim(),
              contact: formContact.trim(),
            }
          : p
      );
      persist(next);
    } else {
      // Add new
      const newPhysician: Physician = {
        id: generateId(),
        name: trimmedName,
        specialty: formSpecialty.trim(),
        contact: formContact.trim(),
      };
      persist([...physicians, newPhysician]);
    }

    resetForm();
  }, [formName, formSpecialty, formContact, editId, physicians, persist, resetForm]);

  const handleDelete = useCallback(
    (id: string) => {
      persist(physicians.filter((p) => p.id !== id));
      // If we were editing this one, close the form
      if (editId === id) resetForm();
    },
    [physicians, editId, persist, resetForm]
  );

  return (
    <div className="apple-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/30">
        <div className="w-5 h-5 rounded-md bg-violet-500/15 flex items-center justify-center ring-1 ring-violet-500/20">
          <Stethoscope className="h-2.5 w-2.5 text-violet-400" />
        </div>
        <h2 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
          Physician Directory
        </h2>
        <div className="flex-1" />
        <span className="text-[11px] text-muted-foreground tabular-nums">
          {physicians.length}
        </span>
      </div>

      <div className="p-4">
        {/* List */}
        {physicians.length === 0 && !showForm ? (
          <div className="flex flex-col items-center py-6">
            <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mb-3 ring-1 ring-border">
              <Stethoscope className="h-5 w-5 text-muted-foreground/30" />
            </div>
            <p className="text-[13px] text-muted-foreground text-center max-w-[240px] leading-relaxed">
              No physicians in your directory. Add physicians for quick access when
              creating patients or referrals.
            </p>
          </div>
        ) : (
          <div className="space-y-2 mb-3">
            {physicians.map((physician) => (
              <div
                key={physician.id}
                className={cn(
                  "flex items-start gap-3 p-3 rounded-xl transition-colors",
                  "bg-[var(--surface-2)] border border-border/20",
                  editId === physician.id && "ring-1 ring-primary/30"
                )}
              >
                {/* Avatar */}
                <div className="w-9 h-9 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0 ring-1 ring-violet-500/15">
                  <Stethoscope className="h-3.5 w-3.5 text-violet-400" />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold text-foreground truncate leading-tight">
                    {physician.name}
                  </p>
                  {physician.specialty && (
                    <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                      {physician.specialty}
                    </p>
                  )}
                  {physician.contact && (
                    <p className="text-[11px] text-primary/70 truncate mt-0.5 flex items-center gap-1">
                      <Phone className="h-2.5 w-2.5 shrink-0" />
                      {physician.contact}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleEdit(physician)}
                    aria-label={`Edit ${physician.name}`}
                    className={cn(
                      "min-w-[44px] min-h-[44px] flex items-center justify-center",
                      "rounded-lg text-muted-foreground/50 hover:text-foreground",
                      "active:bg-[var(--surface-3)] transition-colors"
                    )}
                  >
                    <span className="text-[11px] font-medium text-primary">
                      Edit
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(physician.id)}
                    aria-label={`Delete ${physician.name}`}
                    className={cn(
                      "min-w-[44px] min-h-[44px] flex items-center justify-center",
                      "rounded-lg text-muted-foreground/50 hover:text-rose-400",
                      "active:bg-rose-500/10 transition-colors"
                    )}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Inline form */}
        {showForm && (
          <div className="space-y-3 p-3 rounded-xl bg-[var(--surface-2)] border border-border/30 mb-3 animate-fade-in-up">
            <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
              {editId ? "Edit Physician" : "New Physician"}
            </p>

            {/* Name */}
            <div className="space-y-1.5">
              <label
                htmlFor="physician-form-name"
                className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
              >
                Name <span className="text-rose-400">*</span>
              </label>
              <input
                id="physician-form-name"
                type="text"
                placeholder="Dr. ..."
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                autoFocus
                className={cn(
                  "w-full h-11 px-3 text-[13px] text-foreground rounded-xl",
                  "bg-[var(--surface-3)] border border-border/30",
                  "placeholder:text-muted-foreground/40",
                  "focus:outline-none focus:ring-1 focus:ring-primary/30"
                )}
              />
            </div>

            {/* Specialty */}
            <div className="space-y-1.5">
              <label
                htmlFor="physician-form-specialty"
                className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
              >
                Specialty
              </label>
              <input
                id="physician-form-specialty"
                type="text"
                placeholder="e.g. Vascular Surgery"
                value={formSpecialty}
                onChange={(e) => setFormSpecialty(e.target.value)}
                className={cn(
                  "w-full h-11 px-3 text-[13px] text-foreground rounded-xl",
                  "bg-[var(--surface-3)] border border-border/30",
                  "placeholder:text-muted-foreground/40",
                  "focus:outline-none focus:ring-1 focus:ring-primary/30"
                )}
              />
            </div>

            {/* Contact */}
            <div className="space-y-1.5">
              <label
                htmlFor="physician-form-contact"
                className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"
              >
                Contact
              </label>
              <input
                id="physician-form-contact"
                type="text"
                placeholder="Email or phone"
                value={formContact}
                onChange={(e) => setFormContact(e.target.value)}
                className={cn(
                  "w-full h-11 px-3 text-[13px] text-foreground rounded-xl",
                  "bg-[var(--surface-3)] border border-border/30",
                  "placeholder:text-muted-foreground/40",
                  "focus:outline-none focus:ring-1 focus:ring-primary/30"
                )}
              />
            </div>

            {/* Form actions */}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={resetForm}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 min-h-[44px] rounded-xl",
                  "text-[13px] font-semibold text-muted-foreground",
                  "bg-transparent ring-1 ring-border",
                  "active:bg-[var(--surface-3)] transition-colors"
                )}
              >
                <X className="h-3.5 w-3.5" />
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={!formName.trim()}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 min-h-[44px] rounded-xl",
                  "text-[13px] font-semibold transition-all",
                  formName.trim()
                    ? "bg-primary/15 text-primary ring-1 ring-primary/20 active:bg-primary/25"
                    : "bg-muted text-muted-foreground/30 ring-1 ring-border cursor-not-allowed"
                )}
              >
                <Save className="h-3.5 w-3.5" />
                {editId ? "Update" : "Save"}
              </button>
            </div>
          </div>
        )}

        {/* Add button */}
        {!showForm && (
          <button
            type="button"
            onClick={handleAdd}
            className={cn(
              "w-full flex items-center justify-center gap-2 min-h-[44px] rounded-xl",
              "text-[13px] font-semibold",
              "bg-primary/15 text-primary ring-1 ring-primary/20",
              "active:bg-primary/25 transition-colors"
            )}
          >
            <Plus className="h-4 w-4" />
            Add Physician
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: App Info
// ---------------------------------------------------------------------------

function AppInfoSection() {
  return (
    <div className="apple-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/30">
        <div className="w-5 h-5 rounded-md bg-sky-500/15 flex items-center justify-center ring-1 ring-sky-500/20">
          <Info className="h-2.5 w-2.5 text-sky-400" />
        </div>
        <h2 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.1em]">
          About
        </h2>
      </div>

      <div className="p-4 space-y-4">
        {/* App identity */}
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-primary/15 flex items-center justify-center ring-1 ring-primary/20">
            <Heart className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-[15px] font-bold text-foreground tracking-tight leading-tight">
              Wound Monitor
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              AI-Powered Wound Assessment
            </p>
          </div>
          <div className="ml-auto">
            <span className="text-[11px] font-medium text-muted-foreground bg-[var(--surface-2)] px-2.5 py-1 rounded-full ring-1 ring-border">
              v1.0.0
            </span>
          </div>
        </div>

        {/* Description */}
        <div className="bg-[var(--surface-2)] rounded-xl p-3 border border-border/20">
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            Built for MedGemma Impact Challenge 2026
          </p>
        </div>

        {/* Disclaimer */}
        <div className="flex gap-2.5 p-3 rounded-xl bg-orange-300/5 ring-1 ring-orange-300/10">
          <ShieldAlert className="h-4 w-4 text-orange-300/60 shrink-0 mt-0.5" />
          <p className="text-[11px] text-orange-300/60 leading-relaxed">
            For clinical decision support only. Not a substitute for
            professional medical judgment.
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Export
// ---------------------------------------------------------------------------

export function SettingsPanel({ onSignOut }: { onSignOut?: () => void }) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="animate-slide-up" style={{ animationDelay: "0ms" }}>
        <h2 className="text-[26px] font-bold text-foreground tracking-tight leading-none">
          Settings
        </h2>
        <p className="text-[13px] text-muted-foreground mt-1.5">
          Profile, physicians, and app configuration
        </p>
      </div>

      {/* Sections */}
      <div className="animate-slide-up" style={{ animationDelay: "60ms" }}>
        <NurseProfileSection />
      </div>
      <div className="animate-slide-up" style={{ animationDelay: "120ms" }}>
        <PhysiciansSection />
      </div>
      <div className="animate-slide-up" style={{ animationDelay: "180ms" }}>
        <AppInfoSection />
      </div>

      {/* Sign Out */}
      {onSignOut && (
        <div className="animate-slide-up pt-2" style={{ animationDelay: "240ms" }}>
          <button
            type="button"
            onClick={onSignOut}
            className="w-full flex items-center justify-center gap-2.5 h-12 rounded-2xl
                       bg-red-500/10 text-red-400 text-[14px] font-semibold
                       ring-1 ring-red-500/20 active:bg-red-500/20 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
