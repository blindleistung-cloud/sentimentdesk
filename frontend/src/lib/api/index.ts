export type MarketDataSnapshot = {
  provider: string;
  symbol: string;
  payload: Record<string, unknown>;
  status: string;
};

export type EvidenceMatch = {
  field: string;
  rule_id: string;
  pattern: string;
  snippet: string;
};

export type RatioValue = {
  value?: number | null;
  raw?: string | null;
};

export type OvervaluedStock = {
  rank: number;
  name: string;
  ticker?: string | null;
  pe_ratio?: RatioValue | null;
  pb_ratio?: RatioValue | null;
  pcf_ratio?: RatioValue | null;
  evidence?: EvidenceMatch[];
};

export type CapexItem = {
  company: string;
  year?: number | null;
  amount_usd_billion?: number | null;
  ai_share_percent?: number | null;
  evidence?: EvidenceMatch[];
};

export type RiskCluster = {
  label: string;
  count: number;
  evidence?: EvidenceMatch[];
};

export type IndexMove = {
  index: string;
  percent_change?: number | null;
  points_change?: number | null;
  direction?: "up" | "down" | "flat" | null;
  evidence?: EvidenceMatch[];
};

export type LayerInput = {
  valuation: {
    overvalued_stocks: OvervaluedStock[];
  };
  capex: {
    capex_items: CapexItem[];
    capex_total_usd_billion?: number | null;
    ai_share_percent?: number | null;
  };
  risk: {
    risk_clusters: RiskCluster[];
  };
  market_context: {
    week_label?: string | null;
    index_moves: IndexMove[];
  };
};

export type ScoreResult = {
  valuation_score: number;
  capex_score: number;
  risk_score: number;
  composite_score: number;
  rule_trace: {
    rule_id: string;
    field: string;
    value: string;
    detail: string;
  }[];
};

export type ParseResult = {
  raw_text: string;
  cleaned_text: string;
  layers: LayerInput;
  provider_snapshots: MarketDataSnapshot[];
  scores: ScoreResult;
  evidence: EvidenceMatch[];
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function parseReport(rawText: string): Promise<ParseResult> {
  const response = await fetch(`${API_URL}/api/parse`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ raw_text: rawText }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to parse report.");
  }

  return response.json() as Promise<ParseResult>;
}
