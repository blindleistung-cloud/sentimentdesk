import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { BarChart, Card } from "@tremor/react";
import {
  ApiError,
  parseReport,
  submitManualReport,
  type LayerInput,
  type ParseResult,
  type StockTickerOverride,
  type ValidationResult,
} from "./lib/api";

const scoreFormatter = (value: number) => `${Math.round(value)} / 100`;

type EntryMode = "parse" | "manual";

type ManualStockEntry = {
  rank: number;
  name: string;
  ticker: string;
  pe_ratio: string;
  pb_ratio: string;
  pcf_ratio: string;
};

type ManualCapexEntry = {
  company: string;
  year: string;
  amount_usd_billion: string;
  ai_share_percent: string;
};

type ManualRiskEntry = {
  label: string;
  count: string;
};

type ManualIndexMoveEntry = {
  index: string;
  percent_change: string;
  points_change: string;
  direction: "" | "up" | "down" | "flat";
};

type ManualLayersState = {
  valuation: {
    overvalued_stocks: ManualStockEntry[];
  };
  capex: {
    capex_items: ManualCapexEntry[];
    capex_total_usd_billion: string;
    ai_share_percent: string;
  };
  risk: {
    risk_clusters: ManualRiskEntry[];
  };
  market_context: {
    week_label: string;
    index_moves: ManualIndexMoveEntry[];
  };
};

const createManualLayers = (): ManualLayersState => ({
  valuation: {
    overvalued_stocks: Array.from({ length: 5 }, (_, index) => ({
      rank: index + 1,
      name: "",
      ticker: "",
      pe_ratio: "",
      pb_ratio: "",
      pcf_ratio: "",
    })),
  },
  capex: {
    capex_items: [],
    capex_total_usd_billion: "",
    ai_share_percent: "",
  },
  risk: {
    risk_clusters: [],
  },
  market_context: {
    week_label: "",
    index_moves: [],
  },
});

const parseNumber = (value: string): number | null => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const numberValue = Number(trimmed);
  return Number.isFinite(numberValue) ? numberValue : null;
};

const parseInteger = (value: string): number | null => {
  const numberValue = parseNumber(value);
  if (numberValue === null) {
    return null;
  }
  return Math.trunc(numberValue);
};

const toRatioValue = (value: string) => {
  const numberValue = parseNumber(value);
  return numberValue === null ? null : { value: numberValue };
};

const buildLayerInput = (manual: ManualLayersState): LayerInput => ({
  valuation: {
    overvalued_stocks: manual.valuation.overvalued_stocks.map((stock) => ({
      rank: stock.rank,
      name: stock.name.trim(),
      ticker: stock.ticker.trim() ? stock.ticker.trim().toUpperCase() : null,
      pe_ratio: toRatioValue(stock.pe_ratio),
      pb_ratio: toRatioValue(stock.pb_ratio),
      pcf_ratio: toRatioValue(stock.pcf_ratio),
    })),
  },
  capex: {
    capex_items: manual.capex.capex_items
      .map((item) => ({
        company: item.company.trim(),
        year: parseInteger(item.year),
        amount_usd_billion: parseNumber(item.amount_usd_billion),
        ai_share_percent: parseNumber(item.ai_share_percent),
      }))
      .filter((item) => item.company),
    capex_total_usd_billion: parseNumber(manual.capex.capex_total_usd_billion),
    ai_share_percent: parseNumber(manual.capex.ai_share_percent),
  },
  risk: {
    risk_clusters: manual.risk.risk_clusters
      .map((cluster) => ({
        label: cluster.label.trim(),
        count: parseInteger(cluster.count),
      }))
      .filter((cluster) => cluster.label && cluster.count !== null)
      .map((cluster) => ({
        label: cluster.label,
        count: cluster.count ?? 0,
      })),
  },
  market_context: {
    week_label: manual.market_context.week_label.trim() || null,
    index_moves: manual.market_context.index_moves
      .map((move) => ({
        index: move.index.trim(),
        percent_change: parseNumber(move.percent_change),
        points_change: parseNumber(move.points_change),
        direction: move.direction || null,
      }))
      .filter((move) => move.index),
  },
});

export default function App() {
  const [rawText, setRawText] = useState("");
  const [entryMode, setEntryMode] = useState<EntryMode>("parse");
  const [manualLayers, setManualLayers] = useState<ManualLayersState>(() =>
    createManualLayers(),
  );
  const [result, setResult] = useState<ParseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<ValidationResult | null>(
    null,
  );
  const [tickerOverrides, setTickerOverrides] = useState<Record<string, string>>(
    {},
  );

  useEffect(() => {
    if (!result) {
      setTickerOverrides({});
      return;
    }
    const nextOverrides: Record<string, string> = {};
    result.layers.valuation.overvalued_stocks.forEach((stock) => {
      nextOverrides[stock.name] = stock.ticker ?? "";
    });
    setTickerOverrides(nextOverrides);
  }, [result]);

  useEffect(() => {
    setError(null);
    setValidationError(null);
  }, [entryMode]);

  const scoreSeries = useMemo(() => {
    if (!result) {
      return [];
    }
    return [
      { name: "Valuation", score: result.scores.valuation_score },
      { name: "Capex", score: result.scores.capex_score },
      { name: "Risk", score: result.scores.risk_score },
      { name: "Composite", score: result.scores.composite_score },
    ];
  }, [result]);

  const handleParse = async () => {
    if (!rawText.trim()) {
      setError("Paste a weekly report before parsing.");
      return;
    }
    setLoading(true);
    setError(null);
    setValidationError(null);
    try {
      const parsed = await parseReport(rawText);
      setResult(parsed);
    } catch (err) {
      if (err instanceof ApiError) {
        setValidationError(err.validation ?? null);
        setError(err.message);
      } else {
        const message = err instanceof Error ? err.message : "Parse failed.";
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTickerChange = (name: string, value: string) => {
    setTickerOverrides((prev) => ({ ...prev, [name]: value }));
  };

  const buildTickerOverrides = (): StockTickerOverride[] =>
    Object.entries(tickerOverrides)
      .map(([name, ticker]) => ({ name, ticker: ticker.trim() }))
      .filter((entry) => entry.ticker.length > 0);

  const handleApplyTickers = async () => {
    if (!rawText.trim()) {
      setError("Paste a weekly report before parsing.");
      return;
    }
    const overrides = buildTickerOverrides();
    if (!overrides.length) {
      setError("Add at least one ticker override before updating.");
      return;
    }
    setLoading(true);
    setError(null);
    setValidationError(null);
    try {
      const parsed = await parseReport(rawText, overrides);
      setResult(parsed);
    } catch (err) {
      if (err instanceof ApiError) {
        setValidationError(err.validation ?? null);
        setError(err.message);
      } else {
        const message = err instanceof Error ? err.message : "Parse failed.";
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = async () => {
    if (!rawText.trim()) {
      setError("Paste a weekly report before submitting.");
      return;
    }
    const layers = buildLayerInput(manualLayers);
    setLoading(true);
    setError(null);
    setValidationError(null);
    try {
      const parsed = await submitManualReport(rawText, layers);
      setResult(parsed);
    } catch (err) {
      if (err instanceof ApiError) {
        setValidationError(err.validation ?? null);
        setError(err.message);
      } else {
        const message = err instanceof Error ? err.message : "Manual submit failed.";
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const updateManualStock = (
    index: number,
    field: "name" | "ticker" | "pe_ratio" | "pb_ratio" | "pcf_ratio",
    value: string,
  ) => {
    setManualLayers((prev) => {
      const stocks = [...prev.valuation.overvalued_stocks];
      stocks[index] = { ...stocks[index], [field]: value };
      return {
        ...prev,
        valuation: {
          ...prev.valuation,
          overvalued_stocks: stocks,
        },
      };
    });
  };

  const updateCapexTotals = (
    field: "capex_total_usd_billion" | "ai_share_percent",
    value: string,
  ) => {
    setManualLayers((prev) => ({
      ...prev,
      capex: {
        ...prev.capex,
        [field]: value,
      },
    }));
  };

  const addCapexItem = () => {
    setManualLayers((prev) => ({
      ...prev,
      capex: {
        ...prev.capex,
        capex_items: [
          ...prev.capex.capex_items,
          {
            company: "",
            year: "",
            amount_usd_billion: "",
            ai_share_percent: "",
          },
        ],
      },
    }));
  };

  const updateCapexItem = (
    index: number,
    field: keyof ManualCapexEntry,
    value: string,
  ) => {
    setManualLayers((prev) => {
      const items = [...prev.capex.capex_items];
      items[index] = { ...items[index], [field]: value };
      return {
        ...prev,
        capex: {
          ...prev.capex,
          capex_items: items,
        },
      };
    });
  };

  const removeCapexItem = (index: number) => {
    setManualLayers((prev) => ({
      ...prev,
      capex: {
        ...prev.capex,
        capex_items: prev.capex.capex_items.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      },
    }));
  };

  const addRiskCluster = () => {
    setManualLayers((prev) => ({
      ...prev,
      risk: {
        ...prev.risk,
        risk_clusters: [
          ...prev.risk.risk_clusters,
          { label: "", count: "" },
        ],
      },
    }));
  };

  const updateRiskCluster = (
    index: number,
    field: keyof ManualRiskEntry,
    value: string,
  ) => {
    setManualLayers((prev) => {
      const clusters = [...prev.risk.risk_clusters];
      clusters[index] = { ...clusters[index], [field]: value };
      return {
        ...prev,
        risk: {
          ...prev.risk,
          risk_clusters: clusters,
        },
      };
    });
  };

  const removeRiskCluster = (index: number) => {
    setManualLayers((prev) => ({
      ...prev,
      risk: {
        ...prev.risk,
        risk_clusters: prev.risk.risk_clusters.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      },
    }));
  };

  const updateWeekLabel = (value: string) => {
    setManualLayers((prev) => ({
      ...prev,
      market_context: {
        ...prev.market_context,
        week_label: value,
      },
    }));
  };

  const addIndexMove = () => {
    setManualLayers((prev) => ({
      ...prev,
      market_context: {
        ...prev.market_context,
        index_moves: [
          ...prev.market_context.index_moves,
          {
            index: "",
            percent_change: "",
            points_change: "",
            direction: "",
          },
        ],
      },
    }));
  };

  const updateIndexMove = (
    index: number,
    field: keyof ManualIndexMoveEntry,
    value: string,
  ) => {
    setManualLayers((prev) => {
      const moves = [...prev.market_context.index_moves];
      moves[index] = { ...moves[index], [field]: value };
      return {
        ...prev,
        market_context: {
          ...prev.market_context,
          index_moves: moves,
        },
      };
    });
  };

  const removeIndexMove = (index: number) => {
    setManualLayers((prev) => ({
      ...prev,
      market_context: {
        ...prev.market_context,
        index_moves: prev.market_context.index_moves.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      },
    }));
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const text = await file.text();
    setRawText(text);
    setResult(null);
    setError(null);
    setValidationError(null);
  };

  const activeValidation = validationError ?? result?.validation;

  return (
    <div className="app-shell min-h-screen px-6 py-12 lg:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <header className="fade-in">
          <p className="text-sm uppercase tracking-[0.35em] text-ink/60">
            SentimentDesk v1
          </p>
          <h1 className="section-title mt-4 text-4xl font-semibold text-ink md:text-5xl">
            Weekly Report Intake
          </h1>
          <p className="mt-3 max-w-2xl text-base text-ink/70">
            Paste or upload the market report, parse the deterministic layers, and see
            a fast sentiment score preview.
          </p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="card-panel relative z-10 flex flex-col gap-4 p-6 rise-in">
            <div>
              <h2 className="section-title text-2xl font-semibold text-ink">
                Input
              </h2>
              <p className="text-sm text-ink/70">
                Raw report text is stored as-is. Parsing happens on a cleaned view.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                className={`rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${
                  entryMode === "parse"
                    ? "bg-accent text-white shadow-glow"
                    : "border border-fog bg-white text-ink/70"
                }`}
                onClick={() => setEntryMode("parse")}
                type="button"
              >
                Parse mode
              </button>
              <button
                className={`rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${
                  entryMode === "manual"
                    ? "bg-accent text-white shadow-glow"
                    : "border border-fog bg-white text-ink/70"
                }`}
                onClick={() => setEntryMode("manual")}
                type="button"
              >
                Manual mode
              </button>
            </div>

            <textarea
              className="min-h-[320px] w-full resize-none rounded-xl border border-fog bg-white/70 p-4 text-sm text-ink shadow-sm outline-none transition focus:border-accent"
              placeholder="Paste the weekly report Markdown here..."
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
            />

            {entryMode === "parse" &&
            result?.layers.valuation.overvalued_stocks.length ? (
              <div className="rounded-2xl border border-fog bg-white/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                      Ticker overrides
                    </p>
                    <p className="text-sm text-ink/70">
                      Add tickers to enrich provider fetches.
                    </p>
                  </div>
                  <button
                    className="rounded-xl border border-accent/40 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink shadow-sm transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={handleApplyTickers}
                    disabled={loading}
                  >
                    {loading ? "Updating..." : "Update tickers"}
                  </button>
                </div>
                <div className="mt-3 grid gap-2">
                  {result.layers.valuation.overvalued_stocks.map((stock) => (
                    <div
                      key={`${stock.rank}-${stock.name}`}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-fog bg-white/80 px-3 py-2"
                    >
                      <span className="text-sm font-semibold text-ink">
                        {stock.rank}. {stock.name}
                      </span>
                      <input
                        className="w-28 rounded-lg border border-fog bg-white px-2 py-1 text-xs uppercase tracking-[0.15em] text-ink outline-none transition focus:border-accent"
                        placeholder="TICKER"
                        value={tickerOverrides[stock.name] ?? ""}
                        onChange={(event) =>
                          handleTickerChange(stock.name, event.target.value)
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {entryMode === "manual" ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-fog bg-white/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                        Layer A
                      </p>
                      <p className="text-sm text-ink/70">
                        Exactly five stocks with tickers for provider fetches.
                      </p>
                    </div>
                    <span className="rounded-full border border-fog px-3 py-1 text-xs text-ink/70">
                      5 required
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3">
                    {manualLayers.valuation.overvalued_stocks.map((stock, index) => (
                      <div
                        key={`manual-stock-${stock.rank}`}
                        className="rounded-xl border border-fog bg-white/80 p-3"
                      >
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-xs uppercase tracking-[0.2em] text-ink/60">
                            #{stock.rank}
                          </span>
                          <input
                            className="min-w-[180px] flex-1 rounded-lg border border-fog bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-accent"
                            placeholder="Company name"
                            value={stock.name}
                            onChange={(event) =>
                              updateManualStock(index, "name", event.target.value)
                            }
                          />
                          <input
                            className="w-28 rounded-lg border border-fog bg-white px-2 py-2 text-xs uppercase tracking-[0.15em] text-ink outline-none transition focus:border-accent"
                            placeholder="TICKER"
                            value={stock.ticker}
                            onChange={(event) =>
                              updateManualStock(index, "ticker", event.target.value)
                            }
                          />
                        </div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-3">
                          <input
                            className="rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="P/E"
                            inputMode="decimal"
                            type="number"
                            step="0.01"
                            value={stock.pe_ratio}
                            onChange={(event) =>
                              updateManualStock(index, "pe_ratio", event.target.value)
                            }
                          />
                          <input
                            className="rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="P/B"
                            inputMode="decimal"
                            type="number"
                            step="0.01"
                            value={stock.pb_ratio}
                            onChange={(event) =>
                              updateManualStock(index, "pb_ratio", event.target.value)
                            }
                          />
                          <input
                            className="rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="P/CF"
                            inputMode="decimal"
                            type="number"
                            step="0.01"
                            value={stock.pcf_ratio}
                            onChange={(event) =>
                              updateManualStock(index, "pcf_ratio", event.target.value)
                            }
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-fog bg-white/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                        Layer B
                      </p>
                      <p className="text-sm text-ink/70">
                        Capex details (optional).
                      </p>
                    </div>
                    <button
                      className="rounded-xl border border-fog bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/70 transition hover:border-accent"
                      onClick={addCapexItem}
                      type="button"
                    >
                      Add item
                    </button>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <input
                      className="rounded-lg border border-fog bg-white px-3 py-2 text-xs text-ink outline-none transition focus:border-accent"
                      placeholder="Total capex (USD B)"
                      inputMode="decimal"
                      type="number"
                      step="0.01"
                      value={manualLayers.capex.capex_total_usd_billion}
                      onChange={(event) =>
                        updateCapexTotals(
                          "capex_total_usd_billion",
                          event.target.value,
                        )
                      }
                    />
                    <input
                      className="rounded-lg border border-fog bg-white px-3 py-2 text-xs text-ink outline-none transition focus:border-accent"
                      placeholder="AI share (%)"
                      inputMode="decimal"
                      type="number"
                      step="0.1"
                      value={manualLayers.capex.ai_share_percent}
                      onChange={(event) =>
                        updateCapexTotals("ai_share_percent", event.target.value)
                      }
                    />
                  </div>
                  <div className="mt-3 grid gap-2">
                    {manualLayers.capex.capex_items.length ? (
                      manualLayers.capex.capex_items.map((item, index) => (
                        <div
                          key={`capex-${index}`}
                          className="flex flex-wrap items-center gap-2 rounded-xl border border-fog bg-white/80 p-3"
                        >
                          <input
                            className="min-w-[160px] flex-1 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Company"
                            value={item.company}
                            onChange={(event) =>
                              updateCapexItem(index, "company", event.target.value)
                            }
                          />
                          <input
                            className="w-20 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Year"
                            inputMode="numeric"
                            type="number"
                            value={item.year}
                            onChange={(event) =>
                              updateCapexItem(index, "year", event.target.value)
                            }
                          />
                          <input
                            className="w-24 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="USD B"
                            inputMode="decimal"
                            type="number"
                            step="0.01"
                            value={item.amount_usd_billion}
                            onChange={(event) =>
                              updateCapexItem(
                                index,
                                "amount_usd_billion",
                                event.target.value,
                              )
                            }
                          />
                          <input
                            className="w-20 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="AI %"
                            inputMode="decimal"
                            type="number"
                            step="0.1"
                            value={item.ai_share_percent}
                            onChange={(event) =>
                              updateCapexItem(
                                index,
                                "ai_share_percent",
                                event.target.value,
                              )
                            }
                          />
                          <button
                            className="text-xs font-semibold uppercase tracking-[0.2em] text-warning"
                            onClick={() => removeCapexItem(index)}
                            type="button"
                          >
                            Remove
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-ink/60">No capex items yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-fog bg-white/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                        Layer C
                      </p>
                      <p className="text-sm text-ink/70">
                        Risk cluster counts (optional).
                      </p>
                    </div>
                    <button
                      className="rounded-xl border border-fog bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/70 transition hover:border-accent"
                      onClick={addRiskCluster}
                      type="button"
                    >
                      Add cluster
                    </button>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {manualLayers.risk.risk_clusters.length ? (
                      manualLayers.risk.risk_clusters.map((cluster, index) => (
                        <div
                          key={`risk-${index}`}
                          className="flex flex-wrap items-center gap-2 rounded-xl border border-fog bg-white/80 p-3"
                        >
                          <input
                            className="min-w-[160px] flex-1 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Cluster label"
                            value={cluster.label}
                            onChange={(event) =>
                              updateRiskCluster(index, "label", event.target.value)
                            }
                          />
                          <input
                            className="w-24 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Count"
                            inputMode="numeric"
                            type="number"
                            value={cluster.count}
                            onChange={(event) =>
                              updateRiskCluster(index, "count", event.target.value)
                            }
                          />
                          <button
                            className="text-xs font-semibold uppercase tracking-[0.2em] text-warning"
                            onClick={() => removeRiskCluster(index)}
                            type="button"
                          >
                            Remove
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-ink/60">
                        No risk clusters yet.
                      </p>
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-fog bg-white/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                        Layer D
                      </p>
                      <p className="text-sm text-ink/70">
                        Market context moves (optional).
                      </p>
                    </div>
                    <button
                      className="rounded-xl border border-fog bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/70 transition hover:border-accent"
                      onClick={addIndexMove}
                      type="button"
                    >
                      Add index
                    </button>
                  </div>
                  <div className="mt-3 grid gap-2">
                    <input
                      className="rounded-lg border border-fog bg-white px-3 py-2 text-xs text-ink outline-none transition focus:border-accent"
                      placeholder="Week label"
                      value={manualLayers.market_context.week_label}
                      onChange={(event) => updateWeekLabel(event.target.value)}
                    />
                  </div>
                  <div className="mt-3 grid gap-2">
                    {manualLayers.market_context.index_moves.length ? (
                      manualLayers.market_context.index_moves.map((move, index) => (
                        <div
                          key={`index-${index}`}
                          className="flex flex-wrap items-center gap-2 rounded-xl border border-fog bg-white/80 p-3"
                        >
                          <input
                            className="min-w-[160px] flex-1 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Index"
                            value={move.index}
                            onChange={(event) =>
                              updateIndexMove(index, "index", event.target.value)
                            }
                          />
                          <input
                            className="w-24 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="%"
                            inputMode="decimal"
                            type="number"
                            step="0.01"
                            value={move.percent_change}
                            onChange={(event) =>
                              updateIndexMove(
                                index,
                                "percent_change",
                                event.target.value,
                              )
                            }
                          />
                          <input
                            className="w-24 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            placeholder="Points"
                            inputMode="decimal"
                            type="number"
                            step="0.1"
                            value={move.points_change}
                            onChange={(event) =>
                              updateIndexMove(
                                index,
                                "points_change",
                                event.target.value,
                              )
                            }
                          />
                          <select
                            className="w-28 rounded-lg border border-fog bg-white px-2 py-2 text-xs text-ink outline-none transition focus:border-accent"
                            value={move.direction}
                            onChange={(event) =>
                              updateIndexMove(
                                index,
                                "direction",
                                event.target.value,
                              )
                            }
                          >
                            <option value="">Direction</option>
                            <option value="up">Up</option>
                            <option value="down">Down</option>
                            <option value="flat">Flat</option>
                          </select>
                          <button
                            className="text-xs font-semibold uppercase tracking-[0.2em] text-warning"
                            onClick={() => removeIndexMove(index)}
                            type="button"
                          >
                            Remove
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-ink/60">No index moves yet.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : null}

            {activeValidation && activeValidation.issues.length ? (
              <div className="rounded-2xl border border-fog bg-white/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                      Validation
                    </p>
                    <p className="text-sm text-ink/70">
                      {activeValidation.status === "fail"
                        ? "Fix the blocking issues before saving."
                        : "Review warnings before continuing."}
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-3 py-1 text-xs uppercase tracking-[0.2em] ${
                      activeValidation.status === "fail"
                        ? "border-warning/40 text-warning"
                        : "border-fog text-ink/60"
                    }`}
                  >
                    {activeValidation.status}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-ink/70">
                  {activeValidation.issues.map((issue, index) => (
                    <div
                      key={`${issue.field}-${index}`}
                      className="rounded-lg border border-fog bg-white/90 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span
                          className={`text-[10px] font-semibold uppercase tracking-[0.2em] ${
                            issue.level === "fail"
                              ? "text-warning"
                              : "text-ink/60"
                          }`}
                        >
                          {issue.level}
                        </span>
                        <span className="text-[10px] text-ink/60">
                          {issue.field}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-ink/70">{issue.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <label className="glass-panel flex cursor-pointer items-center gap-2 px-4 py-2 text-sm font-medium text-ink">
                Upload Markdown
                <input
                  type="file"
                  accept=".md,.markdown,.txt"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </label>
              <button
                className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white shadow-glow transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={entryMode === "manual" ? handleManualSubmit : handleParse}
                disabled={loading}
              >
                {loading
                  ? entryMode === "manual"
                    ? "Submitting..."
                    : "Parsing..."
                  : entryMode === "manual"
                    ? "Submit manual report"
                    : "Parse report"}
              </button>
              {error ? (
                <span className="text-sm font-medium text-warning">{error}</span>
              ) : null}
            </div>
          </section>

          <section className="glass-panel relative z-10 flex flex-col gap-5 p-6 rise-in">
            <div>
              <h2 className="section-title text-2xl font-semibold text-ink">
                Score Preview
              </h2>
              <p className="text-sm text-ink/70">
                Initial deterministic scoring before provider enrichment.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Card className="border-none bg-white/80 shadow-card">
                <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                  Composite
                </p>
                <p className="mt-3 text-3xl font-semibold text-ink">
                  {result ? Math.round(result.scores.composite_score) : "--"}
                </p>
              </Card>
              <Card className="border-none bg-white/80 shadow-card">
                <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                  Layer spread
                </p>
                <p className="mt-3 text-3xl font-semibold text-ink">
                  {result ? result.layers.valuation.overvalued_stocks.length : "--"}
                </p>
              </Card>
            </div>

            <Card className="border-none bg-white/80 shadow-card">
              <BarChart
                data={scoreSeries}
                index="name"
                categories={["score"]}
                colors={["cyan"]}
                valueFormatter={scoreFormatter}
                showLegend={false}
                yAxisWidth={48}
              />
            </Card>
          </section>
        </div>

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="card-panel p-6">
            <h3 className="section-title text-xl font-semibold text-ink">Layer A</h3>
            <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
              Valuation
            </p>
            <div className="mt-4 space-y-3 text-sm text-ink/80">
              {result?.layers.valuation.overvalued_stocks.length ? (
                result.layers.valuation.overvalued_stocks.map((stock) => (
                  <div key={`${stock.rank}-${stock.name}`} className="rounded-xl border border-fog p-3">
                    <div className="flex items-center justify-between text-sm font-semibold text-ink">
                      <span>
                        {stock.rank}. {stock.name}
                      </span>
                      <span className="text-xs text-ink/60">
                        {stock.ticker ?? "n/a"}
                      </span>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-ink/70">
                      <span>P/E: {stock.pe_ratio?.value ?? "--"}</span>
                      <span>P/B: {stock.pb_ratio?.value ?? "--"}</span>
                      <span>P/CF: {stock.pcf_ratio?.value ?? "--"}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-ink/60">No valuation matches yet.</p>
              )}
            </div>
          </div>

          <div className="card-panel p-6">
            <h3 className="section-title text-xl font-semibold text-ink">Layer B</h3>
            <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
              Capex
            </p>
            <div className="mt-4 space-y-3 text-sm text-ink/80">
              {result?.layers.capex.capex_items.length ? (
                result.layers.capex.capex_items.map((item, index) => (
                  <div key={`${item.company}-${index}`} className="rounded-xl border border-fog p-3">
                    <div className="flex items-center justify-between text-sm font-semibold text-ink">
                      <span>{item.company}</span>
                      <span className="text-xs text-ink/60">
                        {item.year ?? ""}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-ink/70">
                      ${item.amount_usd_billion ?? "--"}B
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-ink/60">No capex items found.</p>
              )}
            </div>
          </div>

          <div className="card-panel p-6">
            <h3 className="section-title text-xl font-semibold text-ink">Layer C</h3>
            <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
              Risk counts
            </p>
            <div className="mt-4 space-y-3 text-sm text-ink/80">
              {result?.layers.risk.risk_clusters.length ? (
                result.layers.risk.risk_clusters.map((cluster) => (
                  <div key={cluster.label} className="flex items-center justify-between rounded-xl border border-fog px-3 py-2 text-sm">
                    <span className="capitalize">{cluster.label}</span>
                    <span className="font-semibold text-ink">{cluster.count}</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-ink/60">No risk clusters detected.</p>
              )}
            </div>
          </div>
        </section>

        <section className="card-panel p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="section-title text-xl font-semibold text-ink">Layer D</h3>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/60">
                Market context
              </p>
            </div>
            <span className="rounded-full border border-fog px-3 py-1 text-xs text-ink/70">
              {result?.layers.market_context.week_label ?? "Week not detected"}
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {result?.layers.market_context.index_moves.length ? (
              result.layers.market_context.index_moves.map((move) => (
                <div key={move.index} className="rounded-xl border border-fog p-3">
                  <p className="text-sm font-semibold text-ink">{move.index}</p>
                  <p className="text-xs text-ink/70">
                    {move.percent_change ?? "--"}% {move.direction ?? ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink/60">No index moves parsed yet.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
