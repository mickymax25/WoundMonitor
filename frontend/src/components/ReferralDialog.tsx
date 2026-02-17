"use client";

import React, { useState, useCallback } from "react";
import { Send, AlertTriangle, User, Phone, X, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createReferral, getReferralSummaryUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Referral } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Urgency = "routine" | "urgent" | "emergency";

interface ReferralDialogProps {
  open: boolean;
  onClose: () => void;
  assessmentId: string;
  patientId: string;
  patientName: string;
  alertLevel: string;
  alertDetail: string | null;
  referringPhysician?: string | null;
  referringPhysicianPhone?: string | null;
  referringPhysicianEmail?: string | null;
  referringPhysicianPreferredContact?: string | null;
  onReferralCreated: (referral: Referral) => void;
}

// ---------------------------------------------------------------------------
// Urgency pill configuration
// ---------------------------------------------------------------------------

const URGENCY_OPTIONS: {
  value: Urgency;
  label: string;
  activeClasses: string;
}[] = [
  {
    value: "routine",
    label: "Routine",
    activeClasses:
      "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  },
  {
    value: "urgent",
    label: "Urgent",
    activeClasses:
      "bg-orange-300/10 text-orange-300 ring-orange-300/25",
  },
  {
    value: "emergency",
    label: "Emergency",
    activeClasses:
      "bg-red-500/15 text-red-400 ring-red-500/30",
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ReferralDialog({
  open,
  onClose,
  assessmentId,
  patientId,
  patientName,
  alertLevel,
  alertDetail,
  referringPhysician,
  referringPhysicianPhone,
  referringPhysicianEmail,
  referringPhysicianPreferredContact,
  onReferralCreated,
}: ReferralDialogProps) {
  // Default urgency based on alert level
  const defaultUrgency: Urgency =
    alertLevel === "red" ? "emergency" : "urgent";

  // Derive the best contact from preferred method
  const derivedContact =
    referringPhysicianPreferredContact === "email"
      ? referringPhysicianEmail
      : referringPhysicianPhone;

  const [urgency, setUrgency] = useState<Urgency>(defaultUrgency);
  const [physicianName, setPhysicianName] = useState(referringPhysician ?? "");
  const [physicianContact, setPhysicianContact] = useState(derivedContact ?? referringPhysicianPhone ?? referringPhysicianEmail ?? "");
  const [notes, setNotes] = useState(
    alertDetail ? `Clinical alert: ${alertDetail}` : ""
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form state when the dialog opens with new props
  const resetForm = useCallback(() => {
    setUrgency(alertLevel === "red" ? "emergency" : "urgent");
    setPhysicianName(referringPhysician ?? "");
    const contact =
      referringPhysicianPreferredContact === "email"
        ? referringPhysicianEmail
        : referringPhysicianPhone;
    setPhysicianContact(contact ?? referringPhysicianPhone ?? referringPhysicianEmail ?? "");
    setNotes(alertDetail ? `Clinical alert: ${alertDetail}` : "");
    setError(null);
  }, [alertLevel, alertDetail, referringPhysician, referringPhysicianPhone, referringPhysicianEmail, referringPhysicianPreferredContact]);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        onClose();
        // Delay reset so the closing animation completes
        setTimeout(resetForm, 200);
      }
    },
    [onClose, resetForm]
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setError(null);

      try {
        const referral = await createReferral({
          assessment_id: assessmentId,
          patient_id: patientId,
          urgency,
          physician_name: physicianName.trim() || undefined,
          physician_contact: physicianContact.trim() || undefined,
          referral_notes: notes.trim() || undefined,
        });

        onReferralCreated(referral);

        // Attempt Web Share API
        const summaryUrl = getReferralSummaryUrl(referral.id);
        if (typeof navigator !== "undefined" && navigator.share) {
          try {
            await navigator.share({
              title: `Wound Monitor Referral -- ${patientName}`,
              text: `${urgency.toUpperCase()} referral for ${patientName}. Please review the clinical summary.`,
              url: summaryUrl,
            });
          } catch {
            // User cancelled the share sheet or share is unavailable -- not an error
          }
        }

        onClose();
        setTimeout(resetForm, 200);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to create referral."
        );
      } finally {
        setLoading(false);
      }
    },
    [
      assessmentId,
      patientId,
      urgency,
      physicianName,
      physicianContact,
      notes,
      patientName,
      onReferralCreated,
      onClose,
      resetForm,
    ]
  );

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ring-1",
                alertLevel === "red"
                  ? "bg-red-500/15 ring-red-500/25 text-red-400"
                  : "bg-orange-300/10 ring-orange-300/20 text-orange-300"
              )}
            >
              <Send className="h-4 w-4" />
            </div>
            <DialogTitle className="text-[15px]">
              Refer to Physician
            </DialogTitle>
          </div>
          <DialogDescription className="text-[13px] mt-1.5">
            Send a clinical referral for{" "}
            <span className="font-semibold text-foreground">
              {patientName}
            </span>
            .
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5 mt-1">
          {/* Urgency selector */}
          <div className="space-y-2">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
              Urgency
            </Label>
            <div className="flex gap-2">
              {URGENCY_OPTIONS.map((opt) => {
                const isActive = urgency === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setUrgency(opt.value)}
                    className={cn(
                      "flex-1 min-h-[44px] rounded-xl text-[13px] font-semibold ring-1 transition-all",
                      isActive
                        ? opt.activeClasses
                        : "bg-transparent text-muted-foreground ring-border hover:ring-muted-foreground/30"
                    )}
                  >
                    {opt.value === "emergency" && isActive && (
                      <AlertTriangle className="inline h-3.5 w-3.5 mr-1.5 -mt-0.5" />
                    )}
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Physician name */}
          <div className="space-y-2">
            <Label
              htmlFor="referral-physician-name"
              className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              Physician Name
              <span className="ml-1.5 normal-case tracking-normal text-[10px] text-muted-foreground/50">
                (optional)
              </span>
            </Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
              <Input
                id="referral-physician-name"
                placeholder="Dr. ..."
                value={physicianName}
                onChange={(e) => setPhysicianName(e.target.value)}
                className="pl-10 h-11"
              />
            </div>
          </div>

          {/* Physician contact */}
          <div className="space-y-2">
            <Label
              htmlFor="referral-physician-contact"
              className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              Contact
              <span className="ml-1.5 normal-case tracking-normal text-[10px] text-muted-foreground/50">
                (email or phone, optional)
              </span>
            </Label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/40 pointer-events-none" />
              <Input
                id="referral-physician-contact"
                placeholder="email@hospital.org or +1..."
                value={physicianContact}
                onChange={(e) => setPhysicianContact(e.target.value)}
                className="pl-10 h-11"
              />
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label
              htmlFor="referral-notes"
              className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              Referral Notes
            </Label>
            <textarea
              id="referral-notes"
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Additional clinical context for the physician..."
              className={cn(
                "flex w-full rounded-md border border-input bg-background px-3 py-2.5 text-[13px] leading-relaxed",
                "ring-offset-background placeholder:text-muted-foreground/40",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "resize-none"
              )}
            />
          </div>

          {/* Error */}
          {error && (
            <div
              className="flex items-center gap-2 text-[13px] text-red-400 bg-red-500/10 rounded-lg px-3 py-2.5 ring-1 ring-red-500/20"
              role="alert"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {/* Actions */}
          <DialogFooter className="gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={loading}
              className="min-h-[44px]"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className={cn(
                "min-h-[44px] gap-2",
                urgency === "emergency" &&
                  "bg-red-600 hover:bg-red-600/90 text-white"
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Send Referral
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
