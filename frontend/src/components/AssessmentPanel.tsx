"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import {
  Upload,
  Camera,
  Loader2,
  CheckCircle,
  AlertTriangle,
  ImageIcon,
  Trash2,
  Activity,
  Eye,
  TrendingUp,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AudioRecorder } from "@/components/AudioRecorder";
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
    <div className="space-y-2">
      {ANALYSIS_STEPS.map((s, i) => {
        const Icon = s.icon;
        const isDone = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div
            key={i}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg transition-all",
              isDone && "opacity-60",
              isActive && "bg-primary/10 ring-1 ring-primary/20"
            )}
          >
            <div
              className={cn(
                "w-5 h-5 rounded-full flex items-center justify-center shrink-0",
                isDone
                  ? "bg-emerald-500/20"
                  : isActive
                    ? "bg-primary/20"
                    : "bg-muted"
              )}
            >
              {isDone ? (
                <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
              ) : isActive ? (
                <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
              )}
            </div>
            <Icon className={cn(
              "h-3.5 w-3.5 shrink-0",
              isDone
                ? "text-emerald-400/60"
                : isActive
                  ? "text-primary"
                  : "text-muted-foreground/30"
            )} />
            <span
              className={cn(
                "text-xs font-medium",
                isDone
                  ? "text-emerald-400/60"
                  : isActive
                    ? "text-foreground"
                    : "text-muted-foreground/40"
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

export function AssessmentPanel({
  patient,
  onAnalysisComplete,
}: AssessmentPanelProps) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [textNotes, setTextNotes] = useState<string>("");
  const [step, setStep] = useState<AnalysisStep>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showCamera, setShowCamera] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = useCallback(async (file: File) => {
    const compressed = await compressImage(file);
    setImageFile(compressed);
    const url = URL.createObjectURL(compressed);
    setImagePreview(url);
    setStep("idle");
    setErrorMsg(null);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleImageSelect(file);
    },
    [handleImageSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) {
        handleImageSelect(file);
      }
    },
    [handleImageSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const clearImage = useCallback(() => {
    setImageFile(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setStep("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [imagePreview]);

  const handleCameraCapture = useCallback(
    (file: File) => {
      handleImageSelect(file);
      setShowCamera(false);
    },
    [handleImageSelect]
  );

  const handleAnalyze = useCallback(async () => {
    if (!imageFile) return;

    setStep("uploading");
    setErrorMsg(null);

    try {
      const audioFile = audioBlob
        ? new File([audioBlob], "nurse_notes.webm", {
            type: audioBlob.type || "audio/webm",
          })
        : undefined;

      const assessment = await createAssessment(
        patient.id,
        imageFile,
        audioFile,
        undefined, // visitDate
        textNotes.trim() || undefined
      );

      setStep("analyzing");
      const analysisResult = await analyzeAssessment(assessment.id);

      setStep("done");
      onAnalysisComplete(analysisResult);
    } catch (err) {
      setStep("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Analysis failed."
      );
    }
  }, [imageFile, audioBlob, textNotes, patient.id, onAnalysisComplete]);

  const isProcessing = step === "uploading" || step === "analyzing";

  return (
    <>
      {showCamera && (
        <CameraCapture
          onCapture={handleCameraCapture}
          onClose={() => setShowCamera(false)}
        />
      )}

      <div className="space-y-5">
        {/* Section title */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
            <Camera className="h-3.5 w-3.5 text-primary" />
          </div>
          <h3 className="text-[15px] font-bold text-foreground">New Assessment</h3>
        </div>

        {/* Image upload / preview */}
        <div className="apple-card overflow-hidden">
          {imagePreview ? (
            <div className="relative group">
              <img
                src={imagePreview}
                alt="Wound photograph"
                className="w-full max-h-80 object-contain bg-black/30"
              />
              {isProcessing && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center">
                  <div className="w-[280px]">
                    <div className="text-center mb-5">
                      <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-2" />
                      <p className="text-sm text-foreground font-semibold">
                        {step === "uploading" ? "Uploading..." : "Analyzing wound..."}
                      </p>
                    </div>
                    {step === "analyzing" && <AnalysisSteps />}
                  </div>
                </div>
              )}
              {!isProcessing && (
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  className="absolute top-3 right-3 h-10 w-10 md:opacity-0 md:group-hover:opacity-100 transition-opacity shadow-lg rounded-xl"
                  onClick={clearImage}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          ) : (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="p-8 text-center cursor-pointer
                         bg-[var(--surface-2)]
                         hover:bg-[var(--surface-3)]
                         transition-all duration-300"
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ")
                  fileInputRef.current?.click();
              }}
            >
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <ImageIcon className="h-8 w-8 text-primary/50" />
              </div>
              <p className="text-[14px] text-foreground font-semibold mb-1">
                <span className="hidden md:inline">Drop wound photograph here</span>
                <span className="md:hidden">Tap to capture wound photo</span>
              </p>
              <p className="text-xs text-muted-foreground/60">
                <span className="hidden md:inline">or click to browse files</span>
                <span className="md:hidden">or browse your photo library</span>
              </p>
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileInput}
          className="hidden"
          aria-label="Upload wound photograph"
        />

        {/* Action buttons row */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-2 h-11 px-4 rounded-xl
                       bg-[var(--surface-2)] ring-1 ring-border text-[13px] font-medium text-foreground
                       active:scale-[0.97] transition-all
                       disabled:opacity-40"
            onClick={() => fileInputRef.current?.click()}
            disabled={isProcessing}
          >
            <Upload className="h-4 w-4 text-primary" />
            Upload
          </button>

          <button
            type="button"
            className="flex items-center gap-2 h-11 px-4 rounded-xl
                       bg-[var(--surface-2)] ring-1 ring-border text-[13px] font-medium text-foreground
                       active:scale-[0.97] transition-all
                       disabled:opacity-40"
            onClick={() => setShowCamera(true)}
            disabled={isProcessing}
          >
            <Camera className="h-4 w-4 text-primary" />
            Camera
          </button>

          <AudioRecorder
            onRecordingComplete={(blob) => setAudioBlob(blob)}
            disabled={isProcessing}
          />

          {audioBlob && (
            <span className="text-[11px] text-emerald-400 font-semibold px-2.5 py-1.5 bg-emerald-500/10 rounded-lg ring-1 ring-emerald-500/20">
              Audio recorded
            </span>
          )}
        </div>

        {/* Clinical notes */}
        <div>
          <label htmlFor="clinical-notes" className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
            Clinical Notes <span className="normal-case tracking-normal font-normal">(optional)</span>
          </label>
          <textarea
            id="clinical-notes"
            value={textNotes}
            onChange={(e) => setTextNotes(e.target.value)}
            disabled={isProcessing}
            placeholder="Dressing changed, no signs of infection, patient reports mild discomfort..."
            rows={3}
            className="w-full rounded-xl bg-[var(--surface-2)] ring-1 ring-border px-3 py-2.5
                       text-sm text-foreground placeholder:text-muted-foreground/40
                       focus:outline-none focus:ring-2 focus:ring-primary/50
                       disabled:opacity-40 resize-none"
          />
        </div>

        {/* Analyze button */}
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={!imageFile || isProcessing}
          className="w-full flex items-center justify-center gap-2 h-14 rounded-2xl
                     text-[14px] font-bold text-white
                     bg-primary
                     shadow-lg shadow-primary/20
                     active:scale-[0.97] transition-all
                     disabled:opacity-30 disabled:shadow-none disabled:bg-muted disabled:text-muted-foreground"
        >
          {step === "uploading" && (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Uploading assessment...
            </>
          )}
          {step === "analyzing" && (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing wound...
            </>
          )}
          {step === "done" && (
            <>
              <CheckCircle className="h-4 w-4" />
              Analysis Complete
            </>
          )}
          {step === "error" && (
            <>
              <AlertTriangle className="h-4 w-4" />
              Retry Analysis
            </>
          )}
          {step === "idle" && "Analyze Wound"}
        </button>

        {errorMsg && (
          <p className="text-sm text-rose-400" role="alert">
            {errorMsg}
          </p>
        )}
      </div>
    </>
  );
}
