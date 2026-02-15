"use client";

import React, { useState, useCallback, useRef } from "react";
import {
  Upload,
  Camera,
  Loader2,
  CheckCircle,
  AlertTriangle,
  ImageIcon,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AudioRecorder } from "@/components/AudioRecorder";
import { CameraCapture } from "@/components/CameraCapture";
import { createAssessment, analyzeAssessment } from "@/lib/api";
import { compressImage } from "@/lib/utils";
import type { PatientResponse, AnalysisResult } from "@/lib/types";

interface AssessmentPanelProps {
  patient: PatientResponse;
  onAnalysisComplete: (result: AnalysisResult) => void;
}

type AnalysisStep = "idle" | "uploading" | "analyzing" | "done" | "error";

export function AssessmentPanel({
  patient,
  onAnalysisComplete,
}: AssessmentPanelProps) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
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
        audioFile
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
  }, [imageFile, audioBlob, patient.id, onAnalysisComplete]);

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
                  <div className="text-center">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-3">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    </div>
                    <p className="text-sm text-foreground font-semibold">
                      {step === "uploading"
                        ? "Uploading assessment..."
                        : "AI analysis in progress..."}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">This may take a moment</p>
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
              AI analysis in progress...
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
