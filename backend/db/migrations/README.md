# Migration Notes

The backend currently uses `Base.metadata.create_all` on startup. If you have an existing database, apply this change manually:

```sql
ALTER TABLE market_data_snapshots
ADD COLUMN status TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE weekly_reports
ADD COLUMN validation_status TEXT NOT NULL DEFAULT 'pending',
ADD COLUMN validation_issues_json JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE watchlist_items (
    id UUID PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    removed_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE report_stocks (
    id UUID PRIMARY KEY,
    report_id UUID NOT NULL REFERENCES weekly_reports(id),
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    rank INTEGER,
    focus_commentary TEXT,
    mention_snippets_json JSONB,
    pe_ratio DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    pcf_ratio DOUBLE PRECISION,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT report_stocks_report_id_ticker_key UNIQUE (report_id, ticker)
);

CREATE INDEX report_stocks_ticker_idx ON report_stocks (ticker);
```
