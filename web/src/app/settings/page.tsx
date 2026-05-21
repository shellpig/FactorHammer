import type { Metadata } from "next";
import { SettingsPageClient } from "@/components/settings/settings-page-client";

export const metadata: Metadata = {
  title: "設定 | FactorHammer",
  description: "系統設定、API Key 管理與策略 preset。",
};

export default function SettingsPage() {
  return <SettingsPageClient />;
}
