import { useMemo, useState, type ChangeEvent } from "react";
import { BarChart, Card } from "@tremor/react";
import { parseReport, ParseResult } from "./lib/api";

const scoreFormatter = (value: number) => `${Math.round(value)} / 100`;

export default function App() {
  const [rawText, setRawText] = useState("");
  const [result, setResult] = useState<ParseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    try {
      const parsed = await parseReport(rawText);
      setResult(parsed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Parse failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
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
  };

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

            <textarea
              className="min-h-[320px] w-full resize-none rounded-xl border border-fog bg-white/70 p-4 text-sm text-ink shadow-sm outline-none transition focus:border-accent"
              placeholder="Paste the weekly report Markdown here..."
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
            />

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
                onClick={handleParse}
                disabled={loading}
              >
                {loading ? "Parsing..." : "Parse report"}
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
