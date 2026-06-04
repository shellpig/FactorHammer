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

export interface ActiveEtfHoldingsResponse {
  etf_code: string;
  etf_name: string;
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
