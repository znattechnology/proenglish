import type { Metadata, Viewport } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import "@/styles/pe.css";

import { Toaster } from "sonner";
import Providers from "./Provider";
import { Suspense } from "react";
import { AppInstalavel } from "@/components/pe/app/AppInstalavel";

const dmSans = DM_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_FRONTEND_URL || "http://localhost:3000"),
  title: { default: "ProEnglish", template: "%s" },
  description: "Inglês para profissionais em Angola: cursos, prática diária e conversa com um tutor.",
  applicationName: "ProEnglish",
  appleWebApp: { capable: true, title: "ProEnglish", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: "#000066",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-PT" className="relative dark" suppressHydrationWarning>
      <body className={`${dmSans.variable} font-sans antialiased bg-black`} suppressHydrationWarning>
        <Providers>
          <Suspense fallback={null}>{children}</Suspense>
          <AppInstalavel />
          <Toaster richColors closeButton toastOptions={{ style: { background: "#1B1C22", color: "#fff", border: "1px solid #25262F" } }} />
        </Providers>
      </body>
    </html>
  );
}
