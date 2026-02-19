"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { OnboardingScreen } from "@/components/OnboardingScreen";
import { AuthScreen } from "@/components/AuthScreen";

const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  ssr: false,
});

type AppScreen = "splash" | "onboarding" | "auth" | "app";

const AUTH_KEY = "wm_auth";
const ONBOARDED_KEY = "wm_onboarded";

function resolveScreen(): Exclude<AppScreen, "splash"> {
  try {
    const authRaw = localStorage.getItem(AUTH_KEY);
    if (authRaw) {
      const auth = JSON.parse(authRaw);
      if (auth?.loggedIn === true) return "app";
    }
  } catch {
    /* corrupted */
  }

  const onboarded = localStorage.getItem(ONBOARDED_KEY);
  if (onboarded === "true") return "auth";

  return "onboarding";
}

export default function Page() {
  const [screen, setScreen] = useState<AppScreen>("splash");
  const [splashFading, setSplashFading] = useState(false);

  useEffect(() => {
    // Resolve target screen immediately but stay on splash
    const target = resolveScreen();

    // If user is already logged in, skip splash entirely
    if (target === "app") {
      setScreen("app");
      return;
    }

    // Show splash for 2.5s, then fade out over 0.6s
    const fadeTimer = setTimeout(() => setSplashFading(true), 2500);
    const doneTimer = setTimeout(() => setScreen(target), 3100);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(doneTimer);
    };
  }, []);

  const handleOnboardingComplete = useCallback(() => {
    setScreen("auth");
  }, []);

  const handleAuth = useCallback(() => {
    setScreen("app");
  }, []);

  const handleSignOut = useCallback(() => {
    try {
      const authRaw = localStorage.getItem(AUTH_KEY);
      if (authRaw) {
        const auth = JSON.parse(authRaw);
        auth.loggedIn = false;
        localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
      }
    } catch {
      localStorage.removeItem(AUTH_KEY);
    }
    setScreen("auth");
  }, []);

  // ---- Splash screen ----
  if (screen === "splash") {
    return (
      <div
        className={`fixed inset-0 flex items-center justify-center transition-opacity duration-[600ms] ease-out ${
          splashFading ? "opacity-0 scale-[1.02]" : "opacity-100 scale-100"
        }`}
        style={{ transitionProperty: "opacity, transform" }}
      >
        {/* Ambient glow */}
        <div className="absolute w-80 h-80 rounded-full bg-blue-500/[0.08] blur-[80px] splash-glow" />
        <div className="absolute w-48 h-48 rounded-full bg-violet-500/[0.06] blur-[60px] splash-glow" style={{ animationDelay: "200ms" }} />

        {/* Logo + App name */}
        <div className="relative flex flex-col items-center gap-3 splash-logo">
          <img
            src="/LogoWM_V2.png"
            alt="Wound Monitor"
            width={360}
            height={150}
            className="drop-shadow-[0_0_60px_rgba(59,130,246,0.3)]"
          />
          <p className="text-[11px] text-muted-foreground/60 tracking-wide uppercase splash-text">
            AI-Powered Assessment
          </p>
        </div>
      </div>
    );
  }

  if (screen === "onboarding") {
    return (
      <div key="onboarding" className="animate-screen-enter">
        <OnboardingScreen onComplete={handleOnboardingComplete} />
      </div>
    );
  }

  if (screen === "auth") {
    return (
      <div key="auth" className="animate-screen-enter">
        <AuthScreen onAuth={handleAuth} />
      </div>
    );
  }

  return (
    <div key="app" className="animate-screen-enter h-full">
      <Dashboard onSignOut={handleSignOut} />
    </div>
  );
}
