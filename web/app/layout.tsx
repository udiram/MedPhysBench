import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "../src/styles.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const isLocalHost = host.startsWith("localhost") || host.startsWith("127.0.0.1") || host.startsWith("[::1]");
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (isLocalHost ? "http" : "https");
  const metadataBase = new URL(`${protocol}://${host}`);
  return {
    metadataBase,
    title: "MedPhysBench",
    description:
      "A reproducible benchmark for medical-physics reasoning, tools, artifacts, and safe escalation.",
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title: "MedPhysBench",
      description:
        "Can AI do the work—and know when to stop? Reproducible medical-physics AI evaluation.",
      type: "website",
      images: [{ url: "/og.png", width: 1730, height: 909, alt: "MedPhysBench calibration-grid social card" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "MedPhysBench",
      description: "Reproducible medical-physics AI evaluation.",
      images: ["/og.png"],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
