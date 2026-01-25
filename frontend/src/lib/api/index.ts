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

export type StockTickerOverride = {
  name: string;
  ticker: string;
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

export type ValidationIssue = {
  field: string;
  level: "warn" | "fail";
  message: string;
};

export type ValidationResult = {
  status: "ok" | "warn" | "fail";
  issues: ValidationIssue[];
};

export type ProviderJobStatus = "queued" | "running" | "finished" | "failed";

export type ParseResult = {
  raw_text: string;
  cleaned_text: string;
  layers: LayerInput;
  provider_snapshots: MarketDataSnapshot[];
  scores: ScoreResult;
  evidence: EvidenceMatch[];
  validation: ValidationResult;
  provider_job_id?: string | null;
  provider_job_status?: ProviderJobStatus | null;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  validation?: ValidationResult;

  constructor(message: string, status: number, validation?: ValidationResult) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.validation = validation;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const status = response.status;
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const data = (await response.json()) as unknown;
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail?: unknown }).detail
        : data;

    let message = "Request failed.";
    let validation: ValidationResult | undefined;

    const applyDetail = (value: unknown) => {
      if (!value || typeof value !== "object") {
        return;
      }
      const detailObj = value as {
        message?: unknown;
        validation?: unknown;
      };
      if (typeof detailObj.message === "string" && detailObj.message.trim()) {
        message = detailObj.message;
      }
      if (detailObj.validation) {
        validation = detailObj.validation as ValidationResult;
      }
    };

    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = "Request validation failed.";
    } else {
      applyDetail(detail);
    }

    if (data && typeof data === "object") {
      const dataObj = data as { message?: unknown; validation?: unknown };
      if (typeof dataObj.message === "string" && dataObj.message.trim()) {
        message = dataObj.message;
      }
      if (!validation && dataObj.validation) {
        validation = dataObj.validation as ValidationResult;
      }
    }

    return new ApiError(message, status, validation);
  }

  const message = await response.text();
  return new ApiError(message || "Request failed.", status);
}

export async function parseReport(
  rawText: string,
  tickerOverrides?: StockTickerOverride[],
): Promise<ParseResult> {
  const payload: {
    raw_text: string;
    ticker_overrides?: StockTickerOverride[];
  } = { raw_text: rawText };

  if (tickerOverrides && tickerOverrides.length) {
    payload.ticker_overrides = tickerOverrides;
  }

  const response = await fetch(`${API_URL}/api/parse`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await toApiError(response);
  }

  return response.json() as Promise<ParseResult>;
}

export async function submitManualReport(
  rawText: string,
  layers: LayerInput,
): Promise<ParseResult> {
  const response = await fetch(`${API_URL}/api/report/manual`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      raw_text: rawText,
      layers,
    }),
  });

  if (!response.ok) {
    throw await toApiError(response);
  }

  return response.json() as Promise<ParseResult>;
}
