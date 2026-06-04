import type { Metadata } from "next";
import { ActiveEtfPageClient } from "./active-etf-page-client";

export const metadata: Metadata = {
  title: "主動式 ETF 持股追蹤 | FactorHammer",
  description: "追蹤台股主動式 ETF 每日持股變化與相鄰快照差異。",
};

export default function ActiveEtfPage() {
  return <ActiveEtfPageClient />;
}
