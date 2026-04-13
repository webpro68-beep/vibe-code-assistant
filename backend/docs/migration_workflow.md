# Migration Workflow

## When changing models
1. Update SQLAlchemy models
2. Run autogenerate
3. Review the migration file manually
4. Run upgrade head
5. Run API/worker tests
6. Commit model + migration together

## Before opening PR
- check single Alembic head
- upgrade local DB to head
- ensure no schema drift exists
- verify downgrade -1 at least once for non-trivial migrations

## If multiple heads happen
- rebase first
- if unavoidable, create a merge migration explicitly