"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Camera, Upload, Send, CheckCircle2, AlertCircle, X } from "lucide-react";
import { getPatientReportInfo, submitPatientReport } from "@/lib/api";

type Step = "loading" | "ready" | "preview" | "sending" | "done" | "error";

interface PatientInfo {
  patient_name: string;
  wound_type: string | null;
  wound_location: string | null;
}

export default function PatientReportPage({
  params,
}: {
  params: { token: string };
}) {
  const { token } = params;
  const [step, setStep] = useState<Step>("loading");
  const [info, setInfo] = useState<PatientInfo | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getPatientReportInfo(token)
      .then((data) => {
        setInfo(data);
        setStep("ready");
      })
      .catch(() => {
        setErrorMsg("This link is invalid or has expired.");
        setStep("error");
      });
  }, [token]);

  const handleFile = useCallback((file: File) => {
    setImage(file);
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    setStep("preview");
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const clearImage = useCallback(() => {
    setImage(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setStep("ready");
  }, [imagePreview]);

  const handleSubmit = useCallback(async () => {
    if (!image || !token) return;
    setStep("sending");
    try {
      await submitPatientReport(token, image, note || undefined);
      setStep("done");
    } catch {
      setErrorMsg("Failed to send the photo. Please try again.");
      setStep("error");
    }
  }, [image, token, note]);

  // ---- Error state ----
  if (step === "error") {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center px-6 text-center">
        <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>
        <h1 className="text-lg font-semibold text-slate-800 mb-2">Something went wrong</h1>
        <p className="text-sm text-slate-500 max-w-xs">{errorMsg}</p>
        <button
          onClick={() => { setStep("ready"); setErrorMsg(""); }}
          className="mt-6 text-sm text-blue-600 font-medium"
        >
          Try again
        </button>
      </div>
    );
  }

  // ---- Loading state ----
  if (step === "loading") {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center px-6">
        <div className="w-10 h-10 border-3 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
        <p className="mt-4 text-sm text-slate-400">Loading...</p>
      </div>
    );
  }

  // ---- Success state ----
  if (step === "done") {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center px-6 text-center">
        <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mb-5 animate-in zoom-in-50 duration-300">
          <CheckCircle2 className="w-10 h-10 text-emerald-500" />
        </div>
        <h1 className="text-xl font-semibold text-slate-800 mb-2">Photo sent</h1>
        <p className="text-sm text-slate-500 max-w-xs">
          Your nurse will review it shortly. You can close this page or send another photo.
        </p>
        <button
          onClick={() => {
            clearImage();
            setNote("");
            setStep("ready");
          }}
          className="mt-8 px-6 py-3 bg-blue-600 text-white rounded-2xl text-sm font-semibold shadow-lg shadow-blue-600/20 active:scale-95 transition-transform"
        >
          Send another photo
        </button>
      </div>
    );
  }

  // ---- Ready / Preview states ----
  return (
    <div className="min-h-dvh flex flex-col">
      {/* Header */}
      <header className="px-5 pt-safe-top">
        <div className="flex items-center gap-3 py-4">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20">
            <Camera className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold text-slate-800">Wound Monitor</h1>
            <p className="text-[11px] text-slate-400">
              {info ? `For ${info.patient_name}` : "Photo upload"}
            </p>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 px-5 pb-8">
        {/* Instruction card */}
        <div className="mt-2 mb-6 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
          <h2 className="text-base font-semibold text-slate-800 mb-1">
            Send a photo of your wound
          </h2>
          <p className="text-[13px] text-slate-500 leading-relaxed">
            Take a clear photo in good lighting. Your nurse will review it and follow up if needed.
          </p>
        </div>

        {step === "ready" && (
          <div className="space-y-3">
            {/* Camera button */}
            <button
              onClick={() => cameraInputRef.current?.click()}
              className="w-full flex items-center gap-4 p-4 bg-blue-600 text-white rounded-2xl shadow-lg shadow-blue-600/20 active:scale-[0.98] transition-transform"
            >
              <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
                <Camera className="w-6 h-6" />
              </div>
              <div className="text-left">
                <span className="block text-[15px] font-semibold">Take a photo</span>
                <span className="block text-[12px] text-blue-200">Open camera</span>
              </div>
            </button>

            {/* File upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center gap-4 p-4 bg-white text-slate-700 rounded-2xl border border-slate-200 shadow-sm active:scale-[0.98] transition-transform"
            >
              <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
                <Upload className="w-5 h-5 text-slate-500" />
              </div>
              <div className="text-left">
                <span className="block text-[15px] font-semibold">Choose from gallery</span>
                <span className="block text-[12px] text-slate-400">Select an existing photo</span>
              </div>
            </button>

            {/* Hidden inputs */}
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handleFileChange}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>
        )}

        {(step === "preview" || step === "sending") && imagePreview && (
          <div className="space-y-4">
            {/* Image preview */}
            <div className="relative rounded-2xl overflow-hidden border border-slate-200 shadow-sm">
              <img
                src={imagePreview}
                alt="Wound photo preview"
                className="w-full aspect-[4/3] object-cover"
              />
              {step === "preview" && (
                <button
                  onClick={clearImage}
                  className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center"
                >
                  <X className="w-4 h-4 text-white" />
                </button>
              )}
            </div>

            {/* Optional note */}
            <div>
              <label className="block text-[13px] font-medium text-slate-600 mb-1.5">
                Add a note (optional)
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="How are you feeling? Any pain or changes?"
                rows={3}
                className="w-full px-4 py-3 bg-white rounded-xl border border-slate-200 text-sm text-slate-700 placeholder:text-slate-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
                disabled={step === "sending"}
              />
            </div>

            {/* Send button */}
            <button
              onClick={handleSubmit}
              disabled={step === "sending"}
              className="w-full flex items-center justify-center gap-2 py-4 bg-emerald-600 text-white rounded-2xl text-[15px] font-semibold shadow-lg shadow-emerald-600/20 active:scale-[0.98] transition-transform disabled:opacity-60"
            >
              {step === "sending" ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  Send to nurse
                </>
              )}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
