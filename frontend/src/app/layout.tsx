import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SwRegister } from "@/components/SwRegister";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Wound Monitor - AI Wound Assessment",
  description:
    "AI-powered chronic wound assessment and trajectory tracking for clinical professionals.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Wound Monitor",
  },
};

export const viewport: Viewport = {
  themeColor: "#1a2340",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning style={{ backgroundColor: "#151d33", colorScheme: "dark" }}>
      <head>
        <meta name="color-scheme" content="dark" />
        <style dangerouslySetInnerHTML={{ __html: `html,body{background-color:#151d33!important;color-scheme:dark}` }} />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="mobile-web-app-capable" content="yes" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <link rel="apple-touch-startup-image" href="/splash-dark.png" />
      </head>
      <body className={`${inter.variable} font-sans antialiased wc-hero`} suppressHydrationWarning style={{ backgroundColor: "#151d33" }}>
        {children}
        <SwRegister />
      </body>
    </html>
  );
}
