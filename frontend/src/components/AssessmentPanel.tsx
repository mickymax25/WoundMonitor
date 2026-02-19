"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import {
  Upload,
  Camera,
  Loader2,
  CheckCircle,
  AlertTriangle,
  ImageIcon,
  X,
  Activity,
  Eye,
  TrendingUp,
  FileText,
  Mic,
  Square,
} from "lucide-react";
import { CameraCapture } from "@/components/CameraCapture";
import { createAssessment, analyzeAssessment } from "@/lib/api";
import { cn, compressImage } from "@/lib/utils";
import type { PatientResponse, AnalysisResult } from "@/lib/types";

interface AssessmentPanelProps {
  patient: PatientResponse;
  onAnalysisComplete: (result: AnalysisResult) => void;
}

type AnalysisStep = "idle" | "uploading" | "analyzing" | "done" | "error";

const ANALYSIS_STEPS = [
  { label: "Wound classification", icon: Activity },
  { label: "Visual analysis", icon: Eye },
  { label: "Trajectory comparison", icon: TrendingUp },
  { label: "Generating report", icon: FileText },
] as const;

function AnalysisSteps() {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => Math.min(prev + 1, ANALYSIS_STEPS.length - 1));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-1.5">
      {ANALYSIS_STEPS.map((s, i) => {
        const Icon = s.icon;
        const isDone = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div
            key={i}
            className={cn(
              "flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-all",
              isDone && "opacity-50",
              isActive && "bg-primary/10"
            )}
          >
            <div
              className={cn(
                "w-4.5 h-4.5 rounded-full flex items-center justify-center shrink-0",
                isDone ? "bg-emerald-500/20" : isActive ? "bg-primary/20" : "bg-muted"
              )}
            >
              {isDone ? (
                <CheckCircle className="h-3 w-3 text-emerald-400" />
              ) : isActive ? (
                <Loader2 className="h-3 w-3 text-primary animate-spin" />
              ) : (
                <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
              )}
            </div>
            <Icon
              className={cn(
                "h-3 w-3 shrink-0",
                isDone ? "text-emerald-400/60" : isActive ? "text-primary" : "text-muted-foreground/30"
              )}
            />
            <span
              className={cn(
                "text-[11px] font-medium",
                isDone ? "text-emerald-400/60" : isActive ? "text-foreground" : "text-muted-foreground/40"
              )}
            >
              {s.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline Audio Recorder (compact, matches the panel style)
// ---------------------------------------------------------------------------

function InlineAudioRecorder({
  onRecordingComplete,
  hasRecording,
  disabled,
}: {
  onRecordingComplete: (blob: Blob) => void;
  hasRecording: boolean;
  disabled: boolean;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        onRecordingComplete(blob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setDuration(0);
      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
    } catch {
      // Microphone access denied
    }
  }, [onRecordingComplete]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setIsRecording(false);
  }, []);

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  if (isRecording) {
    return (
      <button
        type="button"
        onClick={stopRecording}
        className="flex items-center gap-2 h-10 px-3.5 rounded-xl
                   bg-rose-500/15 text-rose-400 text-[12px] font-semibold
                   ring-1 ring-rose-500/20 active:bg-rose-500/25 transition-colors"
      >
        <span className="h-2 w-2 rounded-full bg-rose-500 animate-recording" />
        <span className="font-mono tabular-nums">{fmt(duration)}</span>
        <Square className="h-3 w-3 ml-0.5" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={startRecording}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 h-7 px-2.5 rounded-full text-[11px] font-semibold transition-colors ring-1",
        hasRecording
          ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/20"
          : "bg-white/[0.06] text-muted-foreground/60 ring-white/[0.10] active:bg-white/[0.10]",
        "disabled:opacity-30"
      )}
    >
      <Mic className="h-3.5 w-3.5" />
      {hasRecording ? "Re-record" : "Voice Notes"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Assessment Panel
// ---------------------------------------------------------------------------

export function AssessmentPanel({
  patient,
  onAnalysisComplete,
}: AssessmentPanelProps) {
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [textNotes, setTextNotes] = useState<string>("");
  const [step, setStep] = useState<AnalysisStep>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showCamera, setShowCamera] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = useCallback(async (file: File) => {
    const compressed = await compressImage(file);
    setImageFiles((prev) => [...prev, compressed]);
    setImagePreviews((prev) => [...prev, URL.createObjectURL(compressed)]);
    setStep("idle");
    setErrorMsg(null);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) {
        Array.from(files).forEach((f) => handleImageSelect(f));
      }
    },
    [handleImageSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) handleImageSelect(file);
    },
    [handleImageSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const clearImage = useCallback(() => {
    imagePreviews.forEach((url) => URL.revokeObjectURL(url));
    setImageFiles([]);
    setImagePreviews([]);
    setStep("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [imagePreviews]);

  const handleCameraCapture = useCallback(
    (file: File) => {
      handleImageSelect(file);
      setShowCamera(false);
    },
    [handleImageSelect]
  );

  const handleAnalyze = useCallback(async () => {
    if (imageFiles.length === 0) return;

    setStep("uploading");
    setErrorMsg(null);

    try {
      const audioFile = audioBlob
        ? new File([audioBlob], "nurse_notes.webm", { type: audioBlob.type || "audio/webm" })
        : undefined;

      const assessment = await createAssessment(
        patient.id,
        imageFiles[0],
        imageFiles.length > 1 ? imageFiles.slice(1) : undefined,
        audioFile,
        undefined,
        textNotes.trim() || undefined
      );

      setStep("analyzing");
      const analysisResult = await analyzeAssessment(assessment.id);

      setStep("done");
      onAnalysisComplete(analysisResult);
    } catch (err) {
      setStep("error");
      setErrorMsg(err instanceof Error ? err.message : "Analysis failed.");
    }
  }, [imageFiles, audioBlob, textNotes, patient.id, onAnalysisComplete]);

  const isProcessing = step === "uploading" || step === "analyzing";

  return (
    <>
      {showCamera && (
        <CameraCapture
          onCapture={handleCameraCapture}
          onClose={() => setShowCamera(false)}
        />
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleFileInput}
        className="hidden"
        aria-label="Upload wound photograph"
      />

      <div className="space-y-3 p-4">
        {/* ── Photo area ── */}
        {imagePreviews.length > 0 ? (
          <div className="relative rounded-2xl overflow-hidden ring-1 ring-border/30">
            <img
              src={imagePreviews[0]}
              alt="Primary wound photograph"
              className="w-full max-h-64 object-contain bg-black/20"
            />
            {/* Additional images strip */}
            {imagePreviews.length > 1 && (
              <div className="flex gap-1.5 p-2 bg-black/20 overflow-x-auto">
                {imagePreviews.map((preview, idx) => (
                  <img
                    key={idx}
                    src={preview}
                    alt={`Photo ${idx + 1}`}
                    className={cn(
                      "w-12 h-12 rounded-lg object-cover ring-1 shrink-0",
                      idx === 0 ? "ring-primary/50" : "ring-border/30"
                    )}
                  />
                ))}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                  className="w-12 h-12 rounded-lg bg-white/5 ring-1 ring-border/30 flex items-center justify-center shrink-0 active:bg-white/10 disabled:opacity-30"
                >
                  <Upload className="h-4 w-4 text-muted-foreground/50" />
                </button>
              </div>
            )}
            {/* Processing overlay */}
            {isProcessing && (
              <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center">
                <div className="w-[260px]">
                  <div className="text-center mb-4">
                    <Loader2 className="h-7 w-7 animate-spin text-primary mx-auto mb-2" />
                    <p className="text-[13px] text-foreground font-semibold">
                      {step === "uploading" ? "Uploading..." : "Analyzing wound..."}
                    </p>
                  </div>
                  {step === "analyzing" && <AnalysisSteps />}
                </div>
              </div>
            )}
            {/* Remove button */}
            {!isProcessing && (
              <button
                type="button"
                onClick={clearImage}
                className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full
                           bg-black/50 backdrop-blur-sm text-white/80
                           flex items-center justify-center
                           active:bg-black/70 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ) : (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="rounded-2xl border-2 border-dashed border-primary/30
                       bg-primary/[0.04]
                       transition-colors duration-200
                       hover:border-primary/50 hover:bg-primary/[0.08]"
          >
            {/* Tap zone */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-8 flex flex-col items-center gap-3"
            >
              <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center ring-1 ring-primary/25 shadow-lg shadow-primary/10">
                <ImageIcon className="h-6 w-6 text-primary" />
              </div>
              <p className="text-[13px] text-foreground font-medium">
                <span className="hidden md:inline">Drop wound photo or click to browse</span>
                <span className="md:hidden">Tap to select wound photo</span>
              </p>
            </button>
            {/* Camera / Upload split buttons */}
            <div className="flex border-t border-primary/15">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isProcessing}
                className="flex-1 flex items-center justify-center gap-2 py-3.5
                           text-[13px] font-semibold text-primary
                           active:bg-primary/10 transition-colors
                           border-r border-primary/15
                           disabled:opacity-30"
              >
                <Upload className="h-4 w-4" />
                Gallery
              </button>
              <button
                type="button"
                onClick={() => setShowCamera(true)}
                disabled={isProcessing}
                className="flex-1 flex items-center justify-center gap-2 py-3.5
                           text-[13px] font-semibold text-primary
                           active:bg-primary/10 transition-colors
                           disabled:opacity-30"
              >
                <Camera className="h-4 w-4" />
                Camera
              </button>
            </div>
          </div>
        )}

        {/* ── Nurse Input ── */}
        <div className="rounded-xl ring-1 ring-white/[0.10] bg-white/[0.03] overflow-hidden">
          <textarea
            value={textNotes}
            onChange={(e) => setTextNotes(e.target.value)}
            disabled={isProcessing}
            placeholder={"Notes or questions for the AI...\ne.g. Should I switch to a foam dressing?"}
            rows={3}
            className="w-full px-3.5 pt-3 pb-1 bg-transparent
                       text-[13px] text-foreground placeholder:text-muted-foreground/40
                       focus:outline-none
                       disabled:opacity-30 resize-none leading-relaxed"
          />
          <div className="flex items-center justify-between px-3 pb-2.5">
            <InlineAudioRecorder
              onRecordingComplete={(blob) => setAudioBlob(blob)}
              hasRecording={audioBlob !== null}
              disabled={isProcessing}
            />
            <span className="text-[10px] text-muted-foreground/30">
              Ask a question to get Clinical Guidance
            </span>
          </div>
        </div>

        {/* ── Analyze CTA ── */}
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={imageFiles.length === 0 || isProcessing}
          className={cn(
            "w-full flex items-center justify-center gap-2 h-12 rounded-2xl",
            "text-[14px] font-bold transition-all active:scale-[0.97]",
            imageFiles.length > 0 && !isProcessing
              ? "bg-primary text-white shadow-lg shadow-primary/25"
              : "bg-white/[0.06] text-foreground/30 ring-1 ring-white/[0.08]"
          )}
        >
          {step === "uploading" && (
            <><Loader2 className="h-4 w-4 animate-spin" /> Uploading...</>
          )}
          {step === "analyzing" && (
            <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing...</>
          )}
          {step === "done" && (
            <><CheckCircle className="h-4 w-4" /> Complete</>
          )}
          {step === "error" && (
            <><AlertTriangle className="h-4 w-4" /> Retry Analysis</>
          )}
          {step === "idle" && "Analyze Wound"}
        </button>

        {errorMsg && (
          <p className="text-[12px] text-rose-400 text-center" role="alert">
            {errorMsg}
          </p>
        )}
      </div>
    </>
  );
}
