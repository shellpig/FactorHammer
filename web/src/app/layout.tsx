// Root layout (Phase 10-B)

import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { ThemeProvider } from "@/components/theme-provider";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "QuantTrader — 台股量化研究",
  description: "台股 / 美股量化交易研究工具：個股分析、回測、AI 問答。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" suppressHydrationWarning>
      <body className={`${inter.variable} ${mono.variable}`}>
        <ThemeProvider defaultTheme="dark">
          <div className="min-h-screen flex">
            <Sidebar />
            {/* Main content — offset left on PC, bottom padding on mobile */}
            <main className="flex-1 lg:pl-60 pb-16 lg:pb-0">
              <div className="container mx-auto px-4 py-6 max-w-7xl">
                {children}
              </div>
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
