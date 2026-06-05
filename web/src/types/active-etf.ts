export interface ActiveEtf {
  code: string;
  name: string;
}

export interface HoldingRow {
  rank: number;
  holding_code: string;
  holding_name: string;
  shares: number;
  weight_pct: number;
  delta_shares: number | null;
}

export interface ChangeRow {
  holding_code: string;
  holding_name: string;
  delta_shares: number;
}

export interface ActiveEtfPremium {
  etf_code: string;
  etf_name: string;
  market_price: number | null;
  estimated_nav: number | null;
  premium_discount_pct: number | null;
  previous_nav: number | null;
  data_date: string;
  data_time: string;
  source: string;
}

export interface ActiveEtfHoldingsResponse {
  etf_code: string;
  etf_name: string;
  premium?: ActiveEtfPremium | null;
  latest_date: string | null;
  previous_date: string | null;
  has_previous: boolean;
  holdings: HoldingRow[];
  changes: {
    buys: ChangeRow[];
    sells: ChangeRow[];
    entries: ChangeRow[];
    exits: ChangeRow[];
  };
}
