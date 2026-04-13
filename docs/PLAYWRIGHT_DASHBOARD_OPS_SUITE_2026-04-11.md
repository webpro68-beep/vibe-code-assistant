# PLAYWRIGHT DASHBOARD OPS SUITE — 2026-04-11

This patch adds E2E coverage for:
- bulk incident actions
- saved views
- effective-access preview
- productivity board

## Added UI selectors
- `bulk-actions-panel`
- `bulk-selected-count`
- `bulk-preview-ack-button`
- `bulk-preview-resolve-button`
- `bulk-ack-button`
- `bulk-resolve-button`
- `bulk-preview-result`
- `bulk-audit-panel`
- `bulk-audit-run-button`
- `bulk-audit-detail`
- `saved-views-panel`
- `saved-view-name-input`
- `saved-view-share-scope-select`
- `saved-view-save-button`
- `saved-view-card`
- `saved-view-apply-button`
- `effective-access-preview`
- `productivity-board`
- `productivity-refresh-button`
- `productivity-teams`
- `productivity-operators`
- `productivity-trends`

## New Playwright flow
The suite creates two failed jobs, turns them into incidents, bulk-resolves them, inspects bulk audit history,
creates a shared saved view, applies it, verifies effective-access preview, and refreshes the productivity board.

## Honest limits
- Browser runtime was not executed in this sandbox.
- Assertions were wired against the current UI contracts and backend routes visible in the uploaded repo.
- If your local seed data differs, productivity counts may vary; the test only requires the board sections to render and the API to respond.
