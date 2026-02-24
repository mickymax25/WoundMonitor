"use client";

import React, { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  Plus,
  User,
  Stethoscope,
  Phone,
  Loader2,
  Activity,
  Building2,
  Mail,
  Check,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { createPatient } from "@/lib/api";
import { WOUND_TYPES, WOUND_LOCATIONS } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { PatientResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Comorbidities grouped by medical category
// ---------------------------------------------------------------------------

const COMORBIDITY_GROUPS = [
  {
    label: "Vascular",
    items: [
      { value: "venous_insufficiency", label: "Venous Insufficiency" },
      { value: "peripheral_neuropathy", label: "Peripheral Neuropathy" },
      { value: "pad", label: "Peripheral Arterial Disease" },
    ],
  },
  {
    label: "Metabolic",
    items: [
      { value: "diabetes", label: "Diabetes" },
      { value: "obesity", label: "Obesity" },
      { value: "malnutrition", label: "Malnutrition" },
    ],
  },
  {
    label: "Systemic",
    items: [
      { value: "hypertension", label: "Hypertension" },
      { value: "anemia", label: "Anemia" },
      { value: "ckd", label: "Chronic Kidney Disease" },
      { value: "immunosuppression", label: "Immunosuppression" },
    ],
  },
  {
    label: "Other",
    items: [
      { value: "leprosy", label: "Leprosy" },
      { value: "smoking", label: "Smoking" },
    ],
  },
] as const;

const GROUP_STYLE: Record<string, { header: string; border: string; check: string; selectedBg: string }> = {
  Vascular: {
    header: "text-rose-400",
    border: "border-l-2 border-l-rose-500/60",
    check: "text-rose-400",
    selectedBg: "bg-rose-500/[0.08]",
  },
  Metabolic: {
    header: "text-amber-400",
    border: "border-l-2 border-l-amber-500/60",
    check: "text-amber-400",
    selectedBg: "bg-amber-500/[0.08]",
  },
  Systemic: {
    header: "text-sky-400",
    border: "border-l-2 border-l-sky-500/60",
    check: "text-sky-400",
    selectedBg: "bg-sky-500/[0.08]",
  },
  Other: {
    header: "text-slate-400",
    border: "border-l-2 border-l-slate-400/50",
    check: "text-slate-400",
    selectedBg: "bg-slate-400/[0.08]",
  },
};

const SPECIALTY_OPTIONS = [
  { value: "vascular_surgery", label: "Vascular Surgery" },
  { value: "wound_care", label: "Wound Care" },
  { value: "dermatology", label: "Dermatology" },
  { value: "endocrinology", label: "Endocrinology" },
  { value: "internal_medicine", label: "Internal Medicine" },
  { value: "orthopedics", label: "Orthopedics" },
  { value: "infectious_disease", label: "Infectious Disease" },
  { value: "other", label: "Other" },
];

const SEX_OPTIONS = [
  { value: "female", label: "F" },
  { value: "male", label: "M" },
];

interface NewPatientDialogProps {
  onCreated: (patient: PatientResponse) => void;
  trigger?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Glass card wrapper
// ---------------------------------------------------------------------------

const GLASS =
  "rounded-2xl backdrop-blur-xl bg-white/[0.05] border border-white/[0.08] p-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_2px_12px_rgba(0,0,0,0.25)]";

function SectionHeader({
  icon: Icon,
  label,
  color,
}: {
  icon: React.ElementType;
  label: string;
  color: string; // e.g. "blue" | "violet" | "emerald"
}) {
  const colorMap: Record<string, { bg: string; text: string; glow: string }> = {
    blue: {
      bg: "bg-blue-500/25",
      text: "text-blue-400",
      glow: "shadow-[0_0_14px_rgba(59,130,246,0.2)]",
    },
    violet: {
      bg: "bg-violet-500/25",
      text: "text-violet-400",
      glow: "shadow-[0_0_14px_rgba(139,92,246,0.2)]",
    },
    emerald: {
      bg: "bg-emerald-500/25",
      text: "text-emerald-400",
      glow: "shadow-[0_0_14px_rgba(16,185,129,0.2)]",
    },
  };
  const c = colorMap[color] ?? colorMap.blue;
  return (
    <div className="flex items-center gap-2.5 mb-4">
      <div
        className={cn(
          "flex items-center justify-center w-7 h-7 rounded-[10px]",
          c.bg,
          c.glow
        )}
      >
        <Icon className={cn("h-3.5 w-3.5", c.text)} />
      </div>
      <p className={cn("text-[11px] font-bold uppercase tracking-[0.08em]", c.text)}>
        {label}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable form primitives
// ---------------------------------------------------------------------------

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-[11px] font-semibold text-foreground/70 uppercase tracking-wider flex items-center gap-1">
        {label}
        {required && <span className="text-rose-400 text-[10px]">*</span>}
      </label>
      {children}
    </div>
  );
}

function FormInput({
  icon: Icon,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: React.ElementType;
}) {
  return (
    <div className="relative">
      {Icon && (
        <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground/30 pointer-events-none" />
      )}
      <input
        {...props}
        className={cn(
          "w-full h-11 text-[13px] text-foreground rounded-xl",
          "bg-white/[0.06] ring-1 ring-white/[0.10]",
          "placeholder:text-foreground/30",
          "focus:outline-none focus:ring-2 focus:ring-primary/40 focus:bg-white/[0.08]",
          Icon ? "pl-10 pr-3" : "px-3",
          props.className
        )}
      />
    </div>
  );
}

function FormSelect({
  value,
  onChange,
  placeholder,
  options,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: { value: string; label: string }[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find((o) => o.value === value)?.label;
  const portalTarget = React.useContext(PickerPortalContext);

  const pickerOverlay = open ? (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center px-6"
      onClick={() => setOpen(false)}
    >
      {/* Scrim */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Sheet */}
      <div
        className="relative w-full max-w-sm rounded-2xl overflow-hidden border border-white/[0.10] shadow-2xl"
        style={{
          background: "linear-gradient(180deg, hsl(226 30% 19%) 0%, hsl(228 32% 14%) 100%)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08]">
          <p className="text-[13px] text-muted-foreground">{placeholder}</p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-[14px] font-semibold text-primary"
          >
            Done
          </button>
        </div>

        {/* Options */}
        <div className="max-h-[50vh] overflow-y-auto py-1">
          {options.map((opt) => {
            const active = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "w-full flex items-center justify-between px-4 h-[46px] text-[15px] transition-colors",
                  "active:bg-white/[0.08]",
                  active
                    ? "text-primary font-medium"
                    : "text-foreground/80"
                )}
              >
                <span>{opt.label}</span>
                {active && <Check className="h-4 w-4 text-primary shrink-0" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "w-full h-11 px-3 text-[13px] rounded-xl text-left",
          "bg-white/[0.06] ring-1 ring-white/[0.10]",
          "active:bg-white/[0.10] transition-colors",
          selectedLabel ? "text-foreground" : "text-foreground/30",
          className
        )}
      >
        {selectedLabel || placeholder}
      </button>

      {/* Portal into DialogContent (outside scrollable form) to stay inside Radix focus trap */}
      {pickerOverlay && portalTarget
        ? createPortal(pickerOverlay, portalTarget)
        : pickerOverlay}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const PickerPortalContext = React.createContext<HTMLDivElement | null>(null);

export function NewPatientDialog({ onCreated, trigger }: NewPatientDialogProps) {
  const pickerPortalRef = React.useRef<HTMLDivElement>(null);
  const [pickerPortalNode, setPickerPortalNode] = React.useState<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdPatient, setCreatedPatient] = useState<PatientResponse | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);

  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [phone, setPhone] = useState("");
  const [woundType, setWoundType] = useState("");
  const [woundLocation, setWoundLocation] = useState("");
  const [comorbidities, setComorbidities] = useState<string[]>([]);
  const [referringPhysician, setReferringPhysician] = useState("");
  const [referringPhysicianSpecialty, setReferringPhysicianSpecialty] = useState("");
  const [referringPhysicianFacility, setReferringPhysicianFacility] = useState("");
  const [referringPhysicianPhone, setReferringPhysicianPhone] = useState("");
  const [referringPhysicianEmail, setReferringPhysicianEmail] = useState("");
  const [referringPhysicianPreferred, setReferringPhysicianPreferred] = useState("");

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
    setSex("");
    setPhone("");
    setWoundType("");
    setWoundLocation("");
    setComorbidities([]);
    setReferringPhysician("");
    setReferringPhysicianSpecialty("");
    setReferringPhysicianFacility("");
    setReferringPhysicianPhone("");
    setReferringPhysicianEmail("");
    setReferringPhysicianPreferred("");
    setError(null);
    setCreatedPatient(null);
    setLinkCopied(false);
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
          sex: sex || null,
          phone: phone.trim() || null,
          wound_type: woundType || null,
          wound_location: woundLocation || null,
          comorbidities,
          referring_physician: referringPhysician.trim() || null,
          referring_physician_specialty: referringPhysicianSpecialty || null,
          referring_physician_facility: referringPhysicianFacility.trim() || null,
          referring_physician_phone: referringPhysicianPhone.trim() || null,
          referring_physician_email: referringPhysicianEmail.trim() || null,
          referring_physician_preferred_contact: referringPhysicianPreferred || null,
        });
        setCreatedPatient(patient);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to create patient."
        );
      } finally {
        setLoading(false);
      }
    },
    [name, age, sex, phone, woundType, woundLocation, comorbidities, referringPhysician, referringPhysicianSpecialty, referringPhysicianFacility, referringPhysicianPhone, referringPhysicianEmail, referringPhysicianPreferred]
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <button
            type="button"
            className="w-full flex items-center justify-center gap-2 h-11 rounded-xl
                       bg-primary/15 text-primary text-[13px] font-semibold
                       ring-1 ring-primary/20 active:bg-primary/25 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Patient
          </button>
        )}
      </DialogTrigger>

      <DialogContent
        hideClose
        className="p-0 gap-0 border-white/[0.06] overflow-hidden
                   fixed inset-0 translate-x-0 translate-y-0 max-w-none h-full rounded-none
                   sm:inset-auto sm:left-[50%] sm:top-[50%] sm:translate-x-[-50%] sm:translate-y-[-50%] sm:max-w-md sm:h-auto sm:max-h-[85vh] sm:rounded-lg
                   flex flex-col"
        style={{
          background: `
            radial-gradient(ellipse 120% 60% at 20% -10%, rgba(56, 120, 255, 0.12) 0%, transparent 60%),
            radial-gradient(ellipse 80% 50% at 85% 20%, rgba(120, 70, 230, 0.08) 0%, transparent 50%),
            radial-gradient(ellipse 90% 40% at 50% 100%, rgba(52, 180, 200, 0.06) 0%, transparent 50%),
            linear-gradient(175deg, hsl(226 38% 16%) 0%, hsl(228 35% 12%) 50%, hsl(230 32% 10%) 100%)
          `,
        }}
      >
        {/* ── Success screen with share link ── */}
        {createdPatient ? (
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
            <div className="w-16 h-16 rounded-full bg-emerald-500/15 flex items-center justify-center mb-5 ring-1 ring-emerald-500/25">
              <Check className="h-8 w-8 text-emerald-400" />
            </div>
            <h2 className="text-[17px] font-bold text-foreground mb-1">Patient created</h2>
            <p className="text-[13px] text-muted-foreground text-center mb-8">
              {createdPatient.name} has been added to your patient list.
            </p>

            {/* Share link card */}
            <div className="w-full max-w-xs space-y-3">
              <div className="rounded-2xl bg-violet-500/10 ring-1 ring-violet-500/20 p-4">
                <p className="text-[13px] font-semibold text-violet-300 mb-1">Photo upload link</p>
                <p className="text-[11px] text-muted-foreground mb-3">
                  Share this link with the patient so they can send wound photos between visits.
                </p>
                <div className="flex items-center gap-2 bg-black/20 rounded-xl px-3 py-2.5 ring-1 ring-white/[0.06]">
                  <p className="flex-1 text-[11px] text-foreground/70 font-mono truncate">
                    {typeof window !== "undefined" ? window.location.origin : ""}/p/{createdPatient.patient_token}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      const link = `${window.location.origin}/p/${createdPatient.patient_token}`;
                      navigator.clipboard.writeText(link).then(() => {
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
              </div>

              <button
                type="button"
                onClick={() => { if (createdPatient) onCreated(createdPatient); setOpen(false); resetForm(); }}
                className="w-full h-12 rounded-2xl bg-primary text-white text-[14px] font-bold
                           shadow-lg shadow-primary/25 active:scale-[0.97] transition-transform"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
        <>
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-4 pb-3 pt-[calc(env(safe-area-inset-top,0px)+10px)] border-b border-white/[0.06]">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-[13px] text-foreground/70 active:text-foreground transition-colors px-1 py-1 -ml-1 min-w-[44px] min-h-[44px] flex items-center gap-1.5"
            aria-label="Discard new patient"
          >
            <X className="h-4 w-4" />
            Discard
          </button>
          <h2 className="text-[15px] font-bold text-foreground">New Patient</h2>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading || !name.trim()}
            className={cn(
              "text-[13px] font-bold px-1 py-1 -mr-1 min-w-[44px] min-h-[44px] flex items-center justify-end transition-colors",
              name.trim() && !loading
                ? "text-primary active:text-primary/70"
                : "text-muted-foreground/50"
            )}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving…
              </span>
            ) : (
              "Save Patient"
            )}
          </button>
        </div>

        {/* ── Form ── */}
        <PickerPortalContext.Provider value={pickerPortalNode}>
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">

          {/* ── Widget: Patient Info (blue) ── */}
          <div className={GLASS}>
            <SectionHeader icon={User} label="Patient Information" color="blue" />
            <div className="space-y-3">
              {/* Row 1: Name */}
              <Field label="Full Name" required>
                <FormInput
                  icon={User}
                  placeholder="Last name, First name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
              </Field>
              {/* Row 2: Age + Sex + Phone */}
              <div className="flex gap-2">
                <div className="w-[72px] shrink-0">
                  <Field label="Age">
                    <FormInput
                      type="number"
                      placeholder="—"
                      min={0}
                      max={150}
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      className="text-center"
                    />
                  </Field>
                </div>
                <div className="w-[72px] shrink-0">
                  <Field label="Sex">
                    <FormSelect
                      value={sex}
                      onChange={setSex}
                      placeholder="—"
                      options={SEX_OPTIONS}
                      className="text-center px-1"
                    />
                  </Field>
                </div>
                <div className="flex-1 min-w-0">
                  <Field label="Phone">
                    <FormInput
                      icon={Phone}
                      type="tel"
                      placeholder="Phone number"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                  </Field>
                </div>
              </div>
            </div>
          </div>

          {/* ── Widget: Wound & Comorbidities (violet) ── */}
          <div className={GLASS}>
            <SectionHeader icon={Activity} label="Wound & Comorbidities" color="violet" />
            <div className="space-y-3">
              {/* Type + Location */}
              <div className="flex gap-2.5">
                <div className="flex-1">
                  <Field label="Wound Type">
                    <FormSelect
                      value={woundType}
                      onChange={setWoundType}
                      placeholder="Select type"
                      options={WOUND_TYPES}
                    />
                  </Field>
                </div>
                <div className="flex-1">
                  <Field label="Location">
                    <FormSelect
                      value={woundLocation}
                      onChange={setWoundLocation}
                      placeholder="Select location"
                      options={WOUND_LOCATIONS}
                    />
                  </Field>
                </div>
              </div>

              {/* Comorbidities — iOS-style grouped checklist */}
              <div className="space-y-3">
                <label className="text-[11px] font-semibold text-foreground/70 uppercase tracking-wider">
                  Comorbidities
                </label>
                {COMORBIDITY_GROUPS.map((group) => {
                  const style = GROUP_STYLE[group.label] ?? GROUP_STYLE.Other;
                  const groupHasSelection = group.items.some((o) => comorbidities.includes(o.value));
                  return (
                    <div key={group.label}>
                      <p className={cn("text-[10px] font-bold uppercase tracking-wider mb-1.5 ml-1", style.header)}>
                        {group.label}
                      </p>
                      <div className={cn("rounded-xl overflow-hidden ring-1 ring-white/[0.08]", style.border)}>
                        {group.items.map((opt, idx) => {
                          const selected = comorbidities.includes(opt.value);
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => toggleComorbidity(opt.value)}
                              className={cn(
                                "w-full flex items-center justify-between px-3.5 h-[42px] text-[13px] transition-colors",
                                "active:bg-white/[0.08]",
                                selected
                                  ? cn("text-foreground font-medium", style.selectedBg)
                                  : "text-foreground/55 bg-white/[0.02]",
                                idx < group.items.length - 1 && "border-b border-white/[0.05]"
                              )}
                            >
                              <span>{opt.label}</span>
                              {selected && (
                                <Check className={cn("h-4 w-4 shrink-0", style.check)} />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── Widget: Referring Physician (emerald) ── */}
          <div className={GLASS}>
            <SectionHeader icon={Stethoscope} label="Referring Physician" color="emerald" />
            <div className="space-y-3">
              <Field label="Physician Name">
                <FormInput
                  icon={Stethoscope}
                  placeholder="Dr. ..."
                  value={referringPhysician}
                  onChange={(e) => setReferringPhysician(e.target.value)}
                />
              </Field>
              <div className="flex gap-2.5">
                <div className="flex-1">
                  <Field label="Specialty">
                    <FormSelect
                      value={referringPhysicianSpecialty}
                      onChange={setReferringPhysicianSpecialty}
                      placeholder="Select"
                      options={SPECIALTY_OPTIONS}
                    />
                  </Field>
                </div>
                <div className="flex-1">
                  <Field label="Facility">
                    <FormInput
                      icon={Building2}
                      placeholder="Hospital / Clinic"
                      value={referringPhysicianFacility}
                      onChange={(e) => setReferringPhysicianFacility(e.target.value)}
                    />
                  </Field>
                </div>
              </div>
              <div className="flex gap-2.5">
                <div className="flex-1">
                  <Field label="Phone">
                    <FormInput
                      icon={Phone}
                      type="tel"
                      placeholder="+1 ..."
                      value={referringPhysicianPhone}
                      onChange={(e) => setReferringPhysicianPhone(e.target.value)}
                    />
                  </Field>
                </div>
                <div className="flex-1">
                  <Field label="Email">
                    <FormInput
                      icon={Mail}
                      type="email"
                      placeholder="doctor@..."
                      value={referringPhysicianEmail}
                      onChange={(e) => setReferringPhysicianEmail(e.target.value)}
                    />
                  </Field>
                </div>
              </div>
              {/* Preferred contact method */}
              <Field label="Preferred Contact">
                <div className="flex gap-1.5">
                  {([
                    { value: "phone", label: "Phone", icon: Phone },
                    { value: "email", label: "Email", icon: Mail },
                    { value: "whatsapp", label: "WhatsApp", icon: Phone },
                  ] as const).map((method) => {
                    const active = referringPhysicianPreferred === method.value;
                    return (
                      <button
                        key={method.value}
                        type="button"
                        onClick={() => setReferringPhysicianPreferred(
                          active ? "" : method.value
                        )}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-1.5 h-10 rounded-xl text-[12px] font-medium transition-all",
                          active
                            ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-400/40"
                            : "bg-white/[0.04] text-foreground/50 ring-1 ring-white/[0.08] active:bg-white/[0.08]"
                        )}
                      >
                        <method.icon className="h-3.5 w-3.5" />
                        {method.label}
                      </button>
                    );
                  })}
                </div>
              </Field>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="pb-1">
              <p className="text-[12px] text-rose-400 text-center" role="alert">
                {error}
              </p>
            </div>
          )}
        </form>
        </PickerPortalContext.Provider>
        {/* Portal target for pickers — inside DialogContent but outside the scrollable form */}
        <div ref={(node) => { (pickerPortalRef as React.MutableRefObject<HTMLDivElement | null>).current = node; setPickerPortalNode(node); }} />
        </>
        )}
      </DialogContent>
    </Dialog>
  );
}
