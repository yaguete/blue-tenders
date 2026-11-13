import type { Metadata } from "next";
import { Schibsted_Grotesk, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import { Shell } from "@/components/shell";

const sans = Schibsted_Grotesk({ subsets: ["latin"], variable: "--font-sans" });
const mono = Spline_Sans_Mono({ subsets: ["latin"], variable: "--font-spline" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: { default: "Blue Tender", template: "%s · Blue Tender" },
  description: "Funding and partners for marine energy projects.",
  icons: {
    icon: [
      {
        url: "/brand/mark.svg",
        type: "image/svg+xml",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/brand/mark-on-dark.png",
        type: "image/png",
        media: "(prefers-color-scheme: dark)",
      },
    ],
    apple: [{ url: "/brand/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={cn("font-sans", sans.variable, mono.variable)} suppressHydrationWarning>
      <body className="antialiased">
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
