import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Send a Photo - Wound Monitor",
  description: "Upload a wound photo for your nurse.",
};

export default function PatientReportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900 font-sans antialiased">
      {children}
    </div>
  );
}
