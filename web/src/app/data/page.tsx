// Data management page (Phase 10-C-1)

import type { Metadata } from "next";
import { DataPageClient } from "@/components/data/data-page-client";

export const metadata: Metadata = {
  title: "資料管理 | FactorHammer",
  description: "管理本機歷史資料、更新與重建。",
};

export default function DataPage() {
  return <DataPageClient />;
}
