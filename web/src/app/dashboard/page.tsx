// Dashboard page (Phase 10-D)

import type { Metadata } from "next";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";

export const metadata: Metadata = {
  title: "個股分析 | QuantTrader",
  description: "股票技術分析、籌碼分析與 AI 劇本。",
};

export default function DashboardPage() {
  return <DashboardPageClient />;
}
