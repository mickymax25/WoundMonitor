"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  Send,
  AlertTriangle,
  User,
  Phone,
  Mail,
  MessageCircle,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Urgency = "routine" | "urgent" | "emergency";

interface ReferralDialogProps {
  open: boolean;
  onClose: () => void;
  patientName: string;
  alertLevel: string;
  alertDetail: string | null;
  referringPhysician?: string | null;
  referringPhysicianPhone?: string | null;
  referringPhysicianEmail?: string | null;
  referringPhysicianPreferredContact?: string | null;
  onReferralSent: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function looksLikeEmail(v: string): boolean {
  return /[^\s@]+@[^\s@]+\.[^\s@]+/.test(v.trim());
}

function looksLikePhone(v: string): boolean {
  const digits = v.replace(/\D/g, "");
  return digits.length >= 6;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ReferralDialog({
  open,
  onClose,
  patientName,
  alertLevel,
  alertDetail,
  referringPhysician,
  referringPhysicianPhone,
  referringPhysicianEmail,
  referringPhysicianPreferredContact,
  onReferralSent,
}: ReferralDialogProps) {
  const defaultUrgency: Urgency =
    alertLevel === "red" ? "emergency" : "urgent";

  const [urgency, setUrgency] = useState<Urgency>(defaultUrgency);
  const [physicianName, setPhysicianName] = useState(referringPhysician ?? "");
  const [contact, setContact] = useState(
    referringPhysicianPhone ?? referringPhysicianEmail ?? ""
  );
  const [notes, setNotes] = useState(
    alertDetail ? `Clinical alert: ${alertDetail}` : ""
  );

  const resetForm = useCallback(() => {
    setUrgency(alertLevel === "red" ? "emergency" : "urgent");
    setPhysicianName(referringPhysician ?? "");
    setContact(referringPhysicianPhone ?? referringPhysicianEmail ?? "");
    setNotes(alertDetail ? `Clinical alert: ${alertDetail}` : "");
  }, [alertLevel, alertDetail, referringPhysician, referringPhysicianPhone, referringPhysicianEmail]);

  const handleClose = useCallback(() => {
    onClose();
    setTimeout(resetForm, 200);
  }, [onClose, resetForm]);

  // Derived values for message building
  const physician = physicianName.trim() || "Physician";
  const patient = patientName || "Patient";
  const urgencyLabel = urgency === "emergency" ? "EMERGENCY" : urgency === "urgent" ? "Urgent" : "Routine";
  const alertInfo = notes.trim() || "Clinical review recommended";

  // Resolve phone and email from the contact field + stored values
  const resolvedPhone = useMemo(() => {
    if (looksLikePhone(contact)) return contact.trim();
    if (referringPhysicianPhone) return referringPhysicianPhone;
    return null;
  }, [contact, referringPhysicianPhone]);

  const resolvedEmail = useMemo(() => {
    if (looksLikeEmail(contact)) return contact.trim();
    if (referringPhysicianEmail) return referringPhysicianEmail;
    return null;
  }, [contact, referringPhysicianEmail]);

  const handleSend = useCallback(
    (channel: "phone" | "whatsapp" | "email") => {
      let url = "";
      if (channel === "phone" && resolvedPhone) {
        const clean = resolvedPhone.replace(/[^+\d]/g, "");
        url = `tel:${clean}`;
      } else if (channel === "whatsapp" && resolvedPhone) {
        const clean = resolvedPhone.replace(/[^+\d]/g, "");
        const text = encodeURIComponent(
          `Wound Monitor — ${urgencyLabel} Referral\n\n${physician}, I am referring ${patient} for review.\n\n${alertInfo}`
        );
        url = `https://wa.me/${clean}?text=${text}`;
      } else if (channel === "email" && resolvedEmail) {
        const subject = encodeURIComponent(`Wound Monitor — ${urgencyLabel} Referral for ${patient}`);
        const body = encodeURIComponent(
          `Dear ${physician},\n\nI am sending a ${urgencyLabel.toLowerCase()} referral for ${patient}.\n\n${alertInfo}\n\nPlease review at your earliest convenience.\n\nBest regards`
        );
        url = `mailto:${resolvedEmail}?subject=${subject}&body=${body}`;
      }
      if (url) {
        window.open(url, "_blank");
        onReferralSent();
        handleClose();
      }
    },
    [resolvedPhone, resolvedEmail, urgencyLabel, physician, patient, alertInfo, onReferralSent, handleClose]
  );

  const preferred = referringPhysicianPreferredContact;

  if (!open) return null;

  const content = (
    <div className="fixed inset-0 z-[9999]" style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0 }}>
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
      />

      {/* Sheet — centered */}
      <div
        className="w-[calc(100%-32px)] max-w-[380px] max-h-[80vh] overflow-y-auto"
        style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}
      >
        <div className="rounded-2xl overflow-hidden bg-[hsl(var(--card))] border-2 border-white/20 shadow-2xl shadow-black/50">

          {/* Header */}
          <div className="px-5 pt-5 pb-4 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                "w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ring-1",
                alertLevel === "red"
                  ? "bg-red-500/15 ring-red-500/25 text-red-400"
                  : "bg-orange-300/10 ring-orange-300/20 text-orange-300"
              )}>
                <Send className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[15px] font-bold text-foreground">Refer to Physician</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">
                  for <span className="text-foreground font-medium">{patientName}</span>
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors -mr-1 -mt-1"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Urgency */}
          <div className="px-5 pb-4">
            <div className="flex gap-2">
              {(["routine", "urgent", "emergency"] as Urgency[]).map((val) => {
                const active = urgency === val;
                const styles: Record<Urgency, string> = {
                  routine: active ? "bg-sky-500/15 text-sky-400 ring-sky-500/30" : "",
                  urgent: active ? "bg-orange-300/10 text-orange-300 ring-orange-300/25" : "",
                  emergency: active ? "bg-red-500/15 text-red-400 ring-red-500/30" : "",
                };
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setUrgency(val)}
                    className={cn(
                      "flex-1 h-10 rounded-xl text-[12px] font-semibold ring-1 transition-all capitalize",
                      active
                        ? styles[val]
                        : "bg-transparent text-muted-foreground/60 ring-white/[0.06] hover:ring-white/[0.12]"
                    )}
                  >
                    {val === "emergency" && active && (
                      <AlertTriangle className="inline h-3 w-3 mr-1 -mt-0.5" />
                    )}
                    {val}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Fields */}
          <div className="px-5 pb-4 space-y-3">
            {/* Physician */}
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/30 pointer-events-none" />
              <input
                placeholder="Physician name"
                value={physicianName}
                onChange={(e) => setPhysicianName(e.target.value)}
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.06] pl-10 pr-4 text-[13px] text-foreground placeholder:text-muted-foreground/30 focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all"
              />
            </div>

            {/* Contact */}
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/30 pointer-events-none" />
              <input
                placeholder="Phone or email"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.06] pl-10 pr-4 text-[13px] text-foreground placeholder:text-muted-foreground/30 focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all"
              />
            </div>

            {/* Notes — compact */}
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Clinical context..."
              className="w-full rounded-xl bg-white/[0.04] border border-white/[0.06] px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground/30 focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all resize-none leading-relaxed"
            />
          </div>

          {/* Channel buttons — always visible */}
          <div className="px-5 pb-5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/40 font-semibold mb-3 text-center">
              Send via
            </p>
            <div className="flex gap-2">
              {/* Call */}
              <button
                type="button"
                disabled={!resolvedPhone}
                onClick={() => handleSend("phone")}
                className={cn(
                  "flex-1 flex flex-col items-center gap-1.5 py-3 rounded-xl ring-1 transition-all active:scale-[0.97]",
                  resolvedPhone
                    ? "bg-emerald-500/10 ring-emerald-500/20 text-emerald-400"
                    : "bg-white/[0.02] ring-white/[0.04] text-muted-foreground/20",
                  preferred === "phone" && resolvedPhone && "ring-2 ring-emerald-500/40"
                )}
              >
                <Phone className="h-5 w-5" />
                <span className="text-[11px] font-semibold">Call</span>
                {preferred === "phone" && resolvedPhone && (
                  <span className="text-[8px] font-medium bg-emerald-500/15 px-1.5 py-0.5 rounded-full -mt-0.5">Preferred</span>
                )}
              </button>

              {/* WhatsApp */}
              <button
                type="button"
                disabled={!resolvedPhone}
                onClick={() => handleSend("whatsapp")}
                className={cn(
                  "flex-1 flex flex-col items-center gap-1.5 py-3 rounded-xl ring-1 transition-all active:scale-[0.97]",
                  resolvedPhone
                    ? "bg-green-500/10 ring-green-500/20 text-green-400"
                    : "bg-white/[0.02] ring-white/[0.04] text-muted-foreground/20",
                  preferred === "whatsapp" && resolvedPhone && "ring-2 ring-green-500/40"
                )}
              >
                <MessageCircle className="h-5 w-5" />
                <span className="text-[11px] font-semibold">WhatsApp</span>
                {preferred === "whatsapp" && resolvedPhone && (
                  <span className="text-[8px] font-medium bg-green-500/15 px-1.5 py-0.5 rounded-full -mt-0.5">Preferred</span>
                )}
              </button>

              {/* Email */}
              <button
                type="button"
                disabled={!resolvedEmail}
                onClick={() => handleSend("email")}
                className={cn(
                  "flex-1 flex flex-col items-center gap-1.5 py-3 rounded-xl ring-1 transition-all active:scale-[0.97]",
                  resolvedEmail
                    ? "bg-sky-500/10 ring-sky-500/20 text-sky-400"
                    : "bg-white/[0.02] ring-white/[0.04] text-muted-foreground/20",
                  preferred === "email" && resolvedEmail && "ring-2 ring-sky-500/40"
                )}
              >
                <Mail className="h-5 w-5" />
                <span className="text-[11px] font-semibold">Email</span>
                {preferred === "email" && resolvedEmail && (
                  <span className="text-[8px] font-medium bg-sky-500/15 px-1.5 py-0.5 rounded-full -mt-0.5">Preferred</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return content;
  return createPortal(content, document.body);
}
