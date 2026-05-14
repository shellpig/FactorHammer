import { describe, expect, it } from "vitest";

import type { DashboardPayloadResponse } from "@/types/analysis";
import mockDashboardPayload from "../../../../docs/mock_dashboard_payload.json";

describe("analysis type schema", () => {
  it("accepts current dashboard mock payload", () => {
    const typedPayload = {
      ...mockDashboardPayload,
      market: mockDashboardPayload.market as DashboardPayloadResponse["market"],
    } satisfies DashboardPayloadResponse;

    expect(typedPayload.symbol).toBe("2330");
    expect(typedPayload.daily_df.length).toBeGreaterThan(0);
    expect(typedPayload.technical.short_term_components.ma).toBeTypeOf("number");
    expect(typedPayload.bid_ask?.label).toBeTypeOf("string");
  });
});
