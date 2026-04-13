# Zero-Downtime Migration Checklist

## 1. General Rules
- Never rename a live column directly if app instances may still read/write old schema.
- Never add a NOT NULL column to a populated table in one step unless a safe default exists and lock impact is acceptable.
- Never drop a column/table/index that old app versions may still use.
- Prefer expand -> migrate/backfill -> switch -> contract.

## 2. Expand Phase
- Add new nullable columns
- Add new tables
- Add new indexes concurrently if DB/infra supports it
- Keep old reads/writes working

## 3. Backfill Phase
- Backfill in SQL or batched jobs
- Make backfill idempotent
- Record assumptions in migration comments

## 4. Switch Phase
- Deploy app code that reads new schema
- Dual-write if needed
- Observe metrics/logs/errors

## 5. Contract Phase
- Remove old columns only after all code paths stop using them
- Prefer a later migration, never same deploy if risk is non-trivial

## 6. Rollback Rules
- Each migration must have a downgrade unless technically impossible
- If downgrade is destructive, document it clearly
- Do not claim safe rollback if data shape changed irreversibly

## 7. Review Checklist
- Upgrade tested on empty DB
- Upgrade tested on existing DB snapshot
- Downgrade tested at least one step
- No accidental drops in autogenerate output
- Constraint/index names stable
- Long-running data migrations separated from schema changes