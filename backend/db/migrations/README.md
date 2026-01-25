# Migration Notes

The backend currently uses `Base.metadata.create_all` on startup. If you have an existing database, apply this change manually:

```sql
ALTER TABLE market_data_snapshots
ADD COLUMN status TEXT NOT NULL DEFAULT 'unknown';
```
