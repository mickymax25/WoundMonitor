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

// ---------------------------------------------------------------------------
// Centralized trajectory / alert configs (used across multiple components)
// ---------------------------------------------------------------------------

export const TRAJECTORY_CONFIG: Record<
  string,
  { label: string; textColor: string; bg: string; icon: string }
> = {
  improving: {
    label: "Improving",
    textColor: "text-emerald-700",
    bg: "bg-emerald-50 border-emerald-200",
    icon: "trending-up",
  },
  stable: {
    label: "Stable",
    textColor: "text-sky-400",
    bg: "bg-sky-500/10 border-sky-500/20",
    icon: "minus",
  },
  deteriorating: {
    label: "Deteriorating",
    textColor: "text-rose-700",
    bg: "bg-rose-50 border-rose-200",
    icon: "trending-down",
  },
  baseline: {
    label: "Baseline",
    textColor: "text-slate-600",
    bg: "bg-slate-50 border-slate-200",
    icon: "circle",
  },
};

export const ALERT_CONFIG: Record<
  string,
  { label: string; textColor: string; bg: string; dotColor: string }
> = {
  green: {
    label: "Normal",
    textColor: "text-emerald-700",
    bg: "bg-emerald-50 border-emerald-200",
    dotColor: "bg-emerald-500",
  },
  yellow: {
    label: "Caution",
    textColor: "text-orange-400",
    bg: "bg-orange-500/10 border-orange-500/20",
    dotColor: "bg-orange-500",
  },
  orange: {
    label: "Warning",
    textColor: "text-orange-700",
    bg: "bg-orange-50 border-orange-200",
    dotColor: "bg-orange-500",
  },
  red: {
    label: "Critical",
    textColor: "text-red-700",
    bg: "bg-red-50 border-red-200",
    dotColor: "bg-red-500",
  },
};

export function trajectoryColor(trajectory: string | null): string {
  return TRAJECTORY_CONFIG[trajectory ?? ""]?.textColor ?? "text-slate-500";
}

export function alertBgColor(level: string | null): string {
  return ALERT_CONFIG[level ?? ""]?.bg ?? "bg-slate-50 border-slate-200";
}

export function alertDotColor(level: string | null): string {
  return ALERT_CONFIG[level ?? ""]?.dotColor ?? "bg-slate-400";
}

// ---------------------------------------------------------------------------
// Image compression — resize + JPEG quality reduction before upload
// ---------------------------------------------------------------------------

export async function compressImage(
  file: File,
  maxSizeMB = 2,
  maxDimension = 1920
): Promise<File> {
  // Skip non-image or already small files
  if (!file.type.startsWith("image/") || file.size <= maxSizeMB * 1024 * 1024) {
    return file;
  }

  return new Promise<File>((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);

      let { width, height } = img;

      // Scale down if needed
      if (width > maxDimension || height > maxDimension) {
        const ratio = Math.min(maxDimension / width, maxDimension / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(file); // fallback: return original
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      // Try progressive quality levels
      const qualities = [0.92, 0.85, 0.75, 0.6, 0.5];
      const targetBytes = maxSizeMB * 1024 * 1024;

      const tryQuality = (idx: number) => {
        const q = qualities[idx] ?? 0.5;
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              resolve(file);
              return;
            }
            if (blob.size <= targetBytes || idx >= qualities.length - 1) {
              resolve(
                new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), {
                  type: "image/jpeg",
                  lastModified: Date.now(),
                })
              );
            } else {
              tryQuality(idx + 1);
            }
          },
          "image/jpeg",
          q
        );
      };

      tryQuality(0);
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load image for compression"));
    };

    img.src = url;
  });
}
