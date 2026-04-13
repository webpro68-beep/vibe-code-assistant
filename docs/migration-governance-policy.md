# Migration Governance Policy

## Purpose

This repository treats Alembic history as governed infrastructure, not as disposable local scaffolding.

The goals are:

- keep migration lineage single-head by default
- prevent broken or ambiguous revision graphs
- ensure migrations are valid on PostgreSQL, not only on SQLite or local fallbacks
- guarantee full-cycle behavior:
  - upgrade head
  - downgrade base
  - re-upgrade head

---

## Core rules

### 1. Single-head is the default invariant

At any shared branch state, the repository must resolve to exactly one Alembic head.

Allowed exception:
- a short-lived branch point may exist inside a private branch during development
- it must be merged before the PR is merged
- CI for the shared branch must pass with exactly one head

### 2. Do not rewrite shared migration history

Once a migration revision is pushed to a shared branch or used by another developer:

- do not edit its revision id
- do not edit its `down_revision` unless performing a controlled repair approved by maintainers
- do not delete it
- do not reorder history by force

Create a new migration or a merge revision instead.

### 3. Merge revisions are explicit governance events

If two revisions produce dual-head:

- do not hide the conflict by editing old files
- create an explicit merge revision
- explain in the PR why the merge exists
- ensure the resulting graph returns to single-head

### 4. PostgreSQL is the source of truth

The migration set is validated against PostgreSQL.

SQLite may be useful for narrow local smoke tests, but it is not the final authority for:
- JSONB
- ENUM
- index/operator behavior
- PostgreSQL-specific DDL semantics

### 5. Full-cycle validation is required

A migration PR is not considered valid unless CI passes:

1. lineage validator
2. `alembic upgrade head`
3. `alembic downgrade base`
4. `alembic upgrade head`

### 6. Every migration must be reversible when practical

Each migration should include a real downgrade path unless the repository has an explicitly documented irreversible policy for that category.

If a migration is intentionally irreversible:
- say so in the migration docstring/comments
- explain why
- obtain maintainer approval

### 7. Models and migrations must stay coherent

If a PR changes:
- ORM models
- SQLAlchemy metadata layout
- import paths used by Alembic env/runtime
- app base/model registration

then the PR must also preserve Alembic bootability and migration validity.

A migration can fail even when the graph is clean if runtime import paths are broken.
