"use client";

import React from "react";
import { Brain, TrendingUp, FileText, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OnboardingScreenProps {
  onComplete: () => void;
}

const FEATURES = [
  {
    icon: Brain,
    title: "BWAT Assessment",
    description: "13-item BWAT scoring with clinical red-flag detection",
    color: "text-blue-400",
    bg: "bg-blue-500/10 ring-blue-500/20",
  },
  {
    icon: TrendingUp,
    title: "Trajectory Tracking",
    description: "Monitor healing progress across visits",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 ring-emerald-500/20",
  },
  {
    icon: FileText,
    title: "Clinical Reports",
    description: "Generate structured reports for physician referral",
    color: "text-violet-400",
    bg: "bg-violet-500/10 ring-violet-500/20",
  },
];

export function OnboardingScreen({ onComplete }: OnboardingScreenProps) {
  const handleGetStarted = () => {
    localStorage.setItem("wm_onboarded", "true");
    onComplete();
  };

  return (
    <div className="fixed inset-0 overflow-y-auto px-8">
      <div className="min-h-[100dvh] flex flex-col items-center justify-center py-12">
      {/* Logo + Motto */}
      <div className="flex flex-col items-center">
        <img
          src="/LogoWM_V2_cropped.png"
          alt="Wound Monitor"
          className="h-14 w-auto max-w-[280px] object-contain mb-3"
        />
        <p className="text-[15px] font-medium tracking-[0.15em] text-muted-foreground/70 uppercase onboard-motto">
          Never miss a sign.
        </p>
      </div>

      {/* Feature pills */}
      <div className="w-full max-w-sm mt-10 space-y-3">
        {FEATURES.map((feat, i) => {
          const Icon = feat.icon;
          return (
            <div
              key={feat.title}
              className="flex items-center gap-3.5 apple-card px-4 py-3.5 onboard-feature"
              style={{ animationDelay: `${800 + i * 200}ms` }}
            >
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ring-1 ${feat.bg}`}
              >
                <Icon className={`h-5 w-5 ${feat.color}`} />
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-foreground leading-tight">
                  {feat.title}
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
                  {feat.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Get Started */}
      <div
        className="w-full max-w-sm mt-10 onboard-feature"
        style={{ animationDelay: "1600ms" }}
      >
        <Button
          onClick={handleGetStarted}
          className="w-full h-12 rounded-2xl text-[15px] font-semibold gap-2"
        >
          Get Started
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Subtle footer */}
      <p
        className="text-[10px] text-muted-foreground/40 mt-6 onboard-feature"
        style={{ animationDelay: "1900ms" }}
      >
        Powered by MedGemma + MedSigLIP + MedASR
      </p>
      </div>
    </div>
  );
}
