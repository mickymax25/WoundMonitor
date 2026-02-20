"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Mail,
  Lock,
  User,
  Building2,
  ScanFace,
  Fingerprint,
  AlertTriangle,
  Loader2,
  Eye,
  EyeOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthScreenProps {
  onAuth: () => void;
}

interface AuthData {
  name: string;
  email: string;
  facility: string;
  role: string;
  loggedIn: boolean;
}

type AuthMode = "login" | "signup";

const AUTH_KEY = "wm_auth";
const BIOMETRIC_KEY = "wm_biometric_registered";

const ROLES = [
  "Wound Care Nurse",
  "Registered Nurse",
  "Nurse Practitioner",
  "Clinical Nurse Specialist",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadAuth(): AuthData | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (raw) return JSON.parse(raw) as AuthData;
  } catch {
    /* corrupted */
  }
  return null;
}

function saveAuth(data: AuthData): void {
  localStorage.setItem(AUTH_KEY, JSON.stringify(data));
}

function isBiometricAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    !!window.PublicKeyCredential &&
    typeof window.isSecureContext !== "undefined" &&
    window.isSecureContext
  );
}

function isBiometricRegistered(): boolean {
  return localStorage.getItem(BIOMETRIC_KEY) === "true";
}

// Simulate biometric auth via WebAuthn
async function requestBiometric(): Promise<boolean> {
  try {
    const credential = await navigator.credentials.create({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        rp: { name: "Wound Monitor", id: window.location.hostname },
        user: {
          id: new Uint8Array(16),
          name: "nurse@woundmonitor.app",
          displayName: "Nurse",
        },
        pubKeyCredParams: [{ alg: -7, type: "public-key" }],
        authenticatorSelection: {
          authenticatorAttachment: "platform",
          userVerification: "required",
        },
        timeout: 60000,
      },
    });
    return !!credential;
  } catch {
    return false;
  }
}

async function verifyBiometric(): Promise<boolean> {
  try {
    const credential = await navigator.credentials.get({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        timeout: 60000,
        userVerification: "required",
        rpId: window.location.hostname,
      },
    });
    return !!credential;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AuthScreen({ onAuth }: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Signup fields
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [facility, setFacility] = useState("");
  const [role, setRole] = useState(ROLES[0]);
  const [password, setPassword] = useState("");

  // Login fields
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Biometric state
  const [biometricAvail, setBiometricAvail] = useState(false);
  const [biometricReady, setBiometricReady] = useState(false);

  // Check if existing account exists — default to login
  useEffect(() => {
    const existing = loadAuth();
    if (existing) {
      setMode("login");
      setLoginEmail(existing.email);
    } else {
      setMode("signup");
    }
    setBiometricAvail(isBiometricAvailable());
    setBiometricReady(isBiometricAvailable() && isBiometricRegistered());
  }, []);

  const handleSignup = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      if (!name.trim() || !email.trim()) {
        setError("Name and email are required.");
        return;
      }

      setLoading(true);

      const authData: AuthData = {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        facility: facility.trim() || "Not specified",
        role,
        loggedIn: true,
      };
      saveAuth(authData);

      // Offer biometric registration
      if (biometricAvail) {
        try {
          const ok = await requestBiometric();
          if (ok) {
            localStorage.setItem(BIOMETRIC_KEY, "true");
          }
        } catch {
          // Biometric not supported or user declined — continue
        }
      }

      setLoading(false);
      onAuth();
    },
    [name, email, facility, role, biometricAvail, onAuth]
  );

  const handleLogin = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      const existing = loadAuth();
      if (!existing) {
        setError("No account found. Please sign up first.");
        return;
      }

      if (existing.email !== loginEmail.trim().toLowerCase()) {
        setError("Email not recognized.");
        return;
      }

      // Password is cosmetic — accept anything
      existing.loggedIn = true;
      saveAuth(existing);
      onAuth();
    },
    [loginEmail, onAuth]
  );

  const handleBiometricLogin = useCallback(async () => {
    setError(null);
    setLoading(true);

    const existing = loadAuth();
    if (!existing) {
      setError("No account found. Please sign up first.");
      setLoading(false);
      return;
    }

    const ok = await verifyBiometric();
    if (ok) {
      existing.loggedIn = true;
      saveAuth(existing);
      onAuth();
    } else {
      setError("Biometric authentication failed. Use email instead.");
    }
    setLoading(false);
  }, [onAuth]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="fixed inset-0 overflow-y-auto flex flex-col items-center px-6 pt-14 pb-8">
      {/* Logo */}
      <div className="flex flex-col items-center mb-6 shrink-0">
        <img
          src="/LogoWM_V2_cropped.png"
          alt="Wound Monitor"
          width={200}
          height={83}
          className="h-14 w-auto"
        />
        <p className="text-[11px] text-muted-foreground/50 tracking-[0.15em] uppercase mt-2">
          Never miss a sign.
        </p>
      </div>

      {/* Card */}
      <div className="w-full max-w-sm apple-card p-5 animate-slide-up">
        {/* Tab toggle */}
        <div className="flex rounded-xl bg-white/[0.04] p-1 mb-5">
          {(["login", "signup"] as AuthMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={cn(
                "flex-1 text-[13px] font-semibold py-2 rounded-lg transition-all",
                mode === m
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {m === "login" ? "Sign In" : "Sign Up"}
            </button>
          ))}
        </div>

        {mode === "signup" ? (
          // ----- SIGNUP -----
          <form onSubmit={handleSignup} className="space-y-3.5">
            {/* Name */}
            <div className="space-y-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Full Name
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Sarah Mitchell"
                  className="pl-10 h-11"
                  required
                />
              </div>
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Email
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="sarah@hospital.org"
                  className="pl-10 h-11"
                  required
                />
              </div>
            </div>

            {/* Facility */}
            <div className="space-y-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Facility
              </Label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                <Input
                  value={facility}
                  onChange={(e) => setFacility(e.target.value)}
                  placeholder="St. Mary's Medical Center"
                  className="pl-10 h-11"
                />
              </div>
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Role
              </Label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className={cn(
                  "flex h-11 w-full rounded-md border border-input bg-background px-3 text-[13px]",
                  "ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  "text-foreground"
                )}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                  className="pl-10 pr-10 h-11"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/50"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 text-[12px] text-red-400 bg-red-500/10 rounded-lg px-3 py-2 ring-1 ring-red-500/20">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                {error}
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-xl text-[14px] font-semibold mt-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Create Account"
              )}
            </Button>
          </form>
        ) : (
          // ----- LOGIN -----
          <div className="space-y-3.5">
            {/* Biometric button — shown first if available */}
            {biometricReady && (
              <Button
                type="button"
                onClick={handleBiometricLogin}
                disabled={loading}
                variant="outline"
                className="w-full h-12 rounded-xl text-[14px] font-semibold gap-2.5
                           border-primary/20 text-primary hover:bg-primary/10"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <ScanFace className="h-5 w-5" />
                    Sign in with Face ID
                  </>
                )}
              </Button>
            )}

            {biometricReady && (
              <div className="flex items-center gap-3 my-1">
                <div className="flex-1 h-px bg-border/50" />
                <span className="text-[11px] text-muted-foreground/50 uppercase tracking-wider">
                  or
                </span>
                <div className="flex-1 h-px bg-border/50" />
              </div>
            )}

            {/* Email/Password form */}
            <form onSubmit={handleLogin} className="space-y-3.5">
              <div className="space-y-1.5">
                <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                  Email
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                  <Input
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="sarah@hospital.org"
                    className="pl-10 h-11"
                    required
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50 pointer-events-none" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="Enter password"
                    className="pl-10 pr-10 h-11"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/50"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 text-[12px] text-red-400 bg-red-500/10 rounded-lg px-3 py-2 ring-1 ring-red-500/20">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 rounded-xl text-[14px] font-semibold"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Sign In"
                )}
              </Button>
            </form>
          </div>
        )}
      </div>

      {/* Demo login */}
      <button
        type="button"
        onClick={() => {
          try {
            const demo: AuthData = {
              name: "Sarah Mitchell, RN",
              email: "sarah@stmarys.med",
              facility: "St. Mary's Medical Center",
              role: "Wound Care Nurse",
              loggedIn: true,
            };
            saveAuth(demo);
          } catch {
            // localStorage may be unavailable (private browsing)
          }
          onAuth();
        }}
        className="mt-5 text-[12px] text-primary/70 hover:text-primary font-medium underline underline-offset-2 animate-slide-up"
        style={{ animationDelay: "200ms" }}
      >
        Demo Login
      </button>

      {/* Toggle link */}
      <p className="text-[12px] text-muted-foreground mt-3 animate-slide-up" style={{ animationDelay: "300ms" }}>
        {mode === "login" ? (
          <>
            Don&apos;t have an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError(null);
              }}
              className="text-primary font-semibold"
            >
              Sign up
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className="text-primary font-semibold"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  );
}
