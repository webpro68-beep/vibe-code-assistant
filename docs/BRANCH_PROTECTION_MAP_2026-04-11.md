# BRANCH PROTECTION MAP — 2026-04-11

## Branches
- `main`: protected, production-grade
- `develop` (optional): integration branch
- `feature/*`: unprotected
- `hotfix/*`: protected by PR into `main`

## Recommended GitHub Branch Protection

### main
- Require a pull request before merging
- Require approvals: 1 minimum
- Dismiss stale pull request approvals when new commits are pushed
- Require review from Code Owners
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Require conversation resolution before merging
- Restrict force pushes
- Restrict deletions
- Include administrators
- Auto-delete head branches after merge: optional

### develop
- Require pull request before merging
- Require status checks:
  - `backend-quick`
  - `frontend-quick`
- Không cần full E2E cho mọi PR nếu `develop` chỉ là integration nhẹ

## Ruleset grouping recommendation

### Ruleset A — Core app/runtime
Applies to:
- `backend/**`
- `frontend/**`
- `e2e/**`
- `edge/**`
- `docker-compose.yml`
- `.github/workflows/**`

Review:
- Technical lead or platform owner

### Ruleset B — Docs only
Applies to:
- `docs/**`

Review:
- lightweight
- no full matrix required

## CODEOWNERS suggestion
- `backend/**` -> backend owner
- `frontend/**` -> frontend owner
- `e2e/**` -> qa/platform owner
- `edge/**` -> platform owner
- `.github/workflows/**` -> platform owner
- `docker-compose.yml` -> platform owner

## Honest note
GitHub branch protection UI không hỗ trợ path-based required checks theo cách tinh vi như workflow engine.
Vì vậy phần "map" này là chiến lược vận hành khuyến nghị, không phải file config duy nhất có thể import 1-click.
