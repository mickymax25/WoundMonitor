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

  // Auto-login: skip onboarding + auth for demo flow
  localStorage.setItem(ONBOARDED_KEY, "true");
  localStorage.setItem(
    AUTH_KEY,
    JSON.stringify({ loggedIn: true, name: "Dr. Demo", role: "nurse" }),
  );
  return "app";
}

export default function Page() {
  const [screen, setScreen] = useState<AppScreen>("splash");
  const [splashFading, setSplashFading] = useState(false);

  useEffect(() => {
    const target = resolveScreen();

    // If already logged in, skip splash
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
          splashFading ? "opacity-0" : "opacity-100"
        }`}
        style={{ transitionProperty: "opacity" }}
      >
        <div className="flex flex-col items-center gap-4 splash-logo">
          <img
            src="/LogoWM_V2_cropped.png"
            alt="Wound Monitor"
            className="h-14 w-auto max-w-[280px] object-contain"
          />
          <p className="text-[15px] font-medium text-muted-foreground/70 tracking-[0.2em] uppercase splash-text">
            Never miss a sign.
          </p>
        </div>
      </div>
    );
  }

  if (screen === "onboarding") {
    return <OnboardingScreen onComplete={handleOnboardingComplete} />;
  }

  if (screen === "auth") {
    return <AuthScreen onAuth={handleAuth} />;
  }

  return (
    <div className="h-full">
      <Dashboard onSignOut={handleSignOut} />
    </div>
  );
}
