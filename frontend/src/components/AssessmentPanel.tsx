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
  TrendingUp,
  TrendingDown,
  Minus,
  Circle,
  AlertCircle,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AudioRecorder } from "@/components/AudioRecorder";
import { CameraCapture } from "@/components/CameraCapture";
import { TimeScoreCard } from "@/components/TimeScoreCard";
import { createAssessment, analyzeAssessment } from "@/lib/api";
import { cn, alertBgColor } from "@/lib/utils";
import type {
  PatientResponse,
  AnalysisResult,
  TimeClassification,
} from "@/lib/types";

interface AssessmentPanelProps {
  patient: PatientResponse;
  onAnalysisComplete: (result: AnalysisResult) => void;
}

type AnalysisStep = "idle" | "uploading" | "analyzing" | "done" | "error";

const TRAJECTORY_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; color: string; bg: string }
> = {
  improving: {
    label: "Improving",
    icon: <TrendingUp className="h-4 w-4" />,
    color: "text-emerald-400",
    bg: "bg-emerald-500/15 border-emerald-500/30",
  },
  stable: {
    label: "Stable",
    icon: <Minus className="h-4 w-4" />,
    color: "text-amber-400",
    bg: "bg-amber-500/15 border-amber-500/30",
  },
  deteriorating: {
    label: "Deteriorating",
    icon: <TrendingDown className="h-4 w-4" />,
    color: "text-rose-400",
    bg: "bg-rose-500/15 border-rose-500/30",
  },
  baseline: {
    label: "Baseline",
    icon: <Circle className="h-4 w-4" />,
    color: "text-slate-400",
    bg: "bg-slate-500/15 border-slate-500/30",
  },
};

function TrajectoryBadge({ trajectory }: { trajectory: string }) {
  const config = TRAJECTORY_CONFIG[trajectory] || TRAJECTORY_CONFIG.baseline;
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-semibold",
        config.bg,
        config.color
      )}
    >
      {config.icon}
      {config.label}
    </div>
  );
}

function AlertBanner({ level, detail }: { level: string; detail: string | null }) {
  if (level === "green") return null;

  const alertConfig: Record<
    string,
    { icon: React.ReactNode; label: string; animate: boolean }
  > = {
    yellow: {
      icon: <Info className="h-4 w-4 text-amber-400" />,
      label: "Advisory",
      animate: false,
    },
    orange: {
      icon: <AlertCircle className="h-4 w-4 text-orange-400" />,
      label: "Warning",
      animate: false,
    },
    red: {
      icon: <AlertTriangle className="h-4 w-4 text-red-400" />,
      label: "Critical Alert",
      animate: true,
    },
  };

  const c = alertConfig[level] || alertConfig.yellow;

  return (
    <div
      className={cn(
        "p-3 rounded-lg border mb-4",
        alertBgColor(level),
        c.animate && "animate-alert-pulse"
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        {c.icon}
        <div>
          <p className="text-sm font-medium">{c.label}</p>
          {detail && (
            <p className="text-xs mt-1 opacity-80">{detail}</p>
          )}
        </div>
      </div>
    </div>
  );
}

const STEPS_LABELS = [
  { key: "uploading", label: "Uploading" },
  { key: "analyzing", label: "AI Analysis" },
  { key: "done", label: "Complete" },
] as const;

function ProgressSteps({ currentStep }: { currentStep: AnalysisStep }) {
  const stepIndex =
    currentStep === "uploading"
      ? 0
      : currentStep === "analyzing"
        ? 1
        : currentStep === "done"
          ? 2
          : -1;

  if (stepIndex < 0) return null;

  return (
    <div className="flex items-center gap-2 mb-4">
      {STEPS_LABELS.map((s, i) => {
        const isActive = i === stepIndex;
        const isComplete = i < stepIndex;
        return (
          <React.Fragment key={s.key}>
            <div className="flex items-center gap-1.5">
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all duration-300",
                  isComplete
                    ? "bg-primary/20 border-primary text-primary"
                    : isActive
                      ? "bg-primary/10 border-primary text-primary animate-pulse"
                      : "bg-accent/50 border-border text-muted-foreground"
                )}
              >
                {isComplete ? (
                  <CheckCircle className="h-3.5 w-3.5" />
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={cn(
                  "text-[10px] font-medium",
                  isActive || isComplete
                    ? "text-foreground"
                    : "text-muted-foreground/50"
                )}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS_LABELS.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-px",
                  isComplete ? "bg-primary/40" : "bg-border"
                )}
              />
            )}
          </React.Fragment>
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
  const [step, setStep] = useState<AnalysisStep>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [showCamera, setShowCamera] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = useCallback((file: File) => {
    setImageFile(file);
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    setResult(null);
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
    setResult(null);
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
    setResult(null);

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

      setResult(analysisResult);
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
        {/* Upload Card */}
        <Card className="border-border/60 shadow-lg shadow-black/10">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold">
                New Assessment
              </CardTitle>
              <span className="text-xs text-muted-foreground bg-accent/50 px-2.5 py-1 rounded-md border border-border">
                {patient.name}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Progress Steps */}
            {(step === "uploading" || step === "analyzing" || step === "done") && (
              <ProgressSteps currentStep={step} />
            )}

            {/* Image Upload Area */}
            {imagePreview ? (
              <div className="relative group rounded-xl overflow-hidden border border-border bg-black/20">
                <img
                  src={imagePreview}
                  alt="Wound photograph"
                  className="w-full max-h-80 object-contain"
                />
                {isProcessing && (
                  <div className="absolute inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center">
                    <div className="text-center">
                      <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-2" />
                      <p className="text-sm text-foreground font-medium">
                        {step === "uploading"
                          ? "Uploading assessment..."
                          : "AI analysis in progress..."}
                      </p>
                    </div>
                  </div>
                )}
                {!isProcessing && (
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    className="absolute top-3 right-3 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
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
                className="border-2 border-dashed border-border/60 rounded-xl p-10 text-center hover:border-primary/40 hover:bg-primary/5 transition-all duration-200 cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ")
                    fileInputRef.current?.click();
                }}
              >
                <div className="w-14 h-14 rounded-2xl bg-accent/50 flex items-center justify-center mx-auto mb-4 border border-border">
                  <ImageIcon className="h-7 w-7 text-muted-foreground/40" />
                </div>
                <p className="text-sm text-foreground/80 font-medium mb-1">
                  Drop wound photograph here
                </p>
                <p className="text-xs text-muted-foreground/50">
                  or click to browse files
                </p>
              </div>
            )}

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
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2 border-border/60"
                onClick={() => fileInputRef.current?.click()}
                disabled={isProcessing}
              >
                <Upload className="h-3.5 w-3.5" />
                Upload
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2 border-border/60"
                onClick={() => setShowCamera(true)}
                disabled={isProcessing}
              >
                <Camera className="h-3.5 w-3.5" />
                Camera
              </Button>

              <AudioRecorder
                onRecordingComplete={(blob) => setAudioBlob(blob)}
                disabled={isProcessing}
              />

              {audioBlob && (
                <Badge variant="info" className="text-xs">
                  Audio recorded
                </Badge>
              )}
            </div>

            {/* Analyze button */}
            <Button
              onClick={handleAnalyze}
              disabled={!imageFile || isProcessing}
              className="w-full gap-2 h-11 text-sm font-semibold"
              size="lg"
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
            </Button>

            {errorMsg && (
              <p className="text-sm text-red-400" role="alert">
                {errorMsg}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        {result && (
          <div className="animate-fade-in-up space-y-4">
            {/* Alert Banner */}
            <AlertBanner
              level={result.alert_level}
              detail={result.alert_detail}
            />

            {/* Trajectory + Change Score */}
            <Card className="border-border/60 shadow-lg shadow-black/10">
              <CardContent className="p-5">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">
                      Wound Trajectory
                    </p>
                    <TrajectoryBadge trajectory={result.trajectory} />
                  </div>
                  {result.change_score !== null && (
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wider">
                        Change Score
                      </p>
                      <span className="text-2xl font-mono font-bold text-foreground">
                        {result.change_score.toFixed(3)}
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* TIME Classification Gauges */}
            <Card className="border-border/60 shadow-lg shadow-black/10">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">
                  TIME Classification
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {(
                    Object.keys(
                      result.time_classification
                    ) as (keyof TimeClassification)[]
                  ).map((dim) => (
                    <TimeScoreCard
                      key={dim}
                      dimension={dim}
                      data={result.time_classification[dim]}
                    />
                  ))}
                </div>

                {result.contradiction_flag && result.contradiction_detail && (
                  <div className="mt-4 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-amber-400">
                          Contradiction Detected
                        </p>
                        <p className="text-xs text-amber-400/80 mt-1">
                          {result.contradiction_detail}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
