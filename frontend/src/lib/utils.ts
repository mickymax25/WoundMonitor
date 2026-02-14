import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateShort(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function scoreToPercent(score: number): number {
  return Math.round(score * 100);
}

export function trajectoryColor(
  trajectory: string | null
): string {
  switch (trajectory) {
    case "improving":
      return "text-emerald-500";
    case "stable":
      return "text-amber-500";
    case "deteriorating":
      return "text-rose-500";
    default:
      return "text-slate-400";
  }
}

export function alertBgColor(level: string | null): string {
  switch (level) {
    case "green":
      return "bg-emerald-500/10 border-emerald-500/30";
    case "yellow":
      return "bg-amber-500/10 border-amber-500/30";
    case "orange":
      return "bg-orange-500/10 border-orange-500/30";
    case "red":
      return "bg-red-500/10 border-red-500/30";
    default:
      return "bg-slate-500/10 border-slate-500/30";
  }
}

export function alertDotColor(level: string | null): string {
  switch (level) {
    case "green":
      return "bg-emerald-500";
    case "yellow":
      return "bg-amber-500";
    case "orange":
      return "bg-orange-500";
    case "red":
      return "bg-red-500";
    default:
      return "bg-slate-500";
  }
}
