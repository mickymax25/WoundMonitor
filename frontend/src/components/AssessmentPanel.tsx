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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AudioRecorder } from "@/components/AudioRecorder";
import { CameraCapture } from "@/components/CameraCapture";
import { TimeScoreCard } from "@/components/TimeScoreCard";
import { createAssessment, analyzeAssessment } from "@/lib/api";
import { cn, trajectoryColor } from "@/lib/utils";
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

function TrajectoryDisplay({ trajectory }: { trajectory: string }) {
  const labels: Record<string, string> = {
    improving: "Improving",
    stable: "Stable",
    deteriorating: "Deteriorating",
    baseline: "Baseline",
  };
  return (
    <span
      className={cn(
        "text-lg font-semibold capitalize",
        trajectoryColor(trajectory)
      )}
    >
      {labels[trajectory] || trajectory}
    </span>
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

      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                New Assessment
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                for {patient.name}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Image Upload Area */}
            {imagePreview ? (
              <div className="relative group">
                <img
                  src={imagePreview}
                  alt="Wound photograph"
                  className="w-full max-h-64 object-contain rounded-lg border border-border"
                />
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  className="absolute top-2 right-2 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={clearImage}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ")
                    fileInputRef.current?.click();
                }}
              >
                <ImageIcon className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground mb-1">
                  Drag and drop wound photograph here
                </p>
                <p className="text-xs text-muted-foreground/60">
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
                className="gap-2"
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
                className="gap-2"
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
              className="w-full gap-2"
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
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  TIME Classification
                </CardTitle>
                <TrajectoryDisplay trajectory={result.trajectory} />
              </div>
              {result.change_score !== null && (
                <p className="text-xs text-muted-foreground">
                  Change score:{" "}
                  <span className="font-mono">
                    {result.change_score.toFixed(3)}
                  </span>
                </p>
              )}
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
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
        )}
      </div>
    </>
  );
}
