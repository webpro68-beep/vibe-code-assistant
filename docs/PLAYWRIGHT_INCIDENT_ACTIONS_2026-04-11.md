# PLAYWRIGHT INCIDENT ACTIONS PATCH — 2026-04-11

This patch adds a full incident workflow action E2E on the dashboard drawer:

- acknowledge
- assign
- mute
- resolve
- reopen

It verifies:
- backend incident history reflects each action
- incident state updates after each action
- drawer workflow history renders each persisted action
- projected timeline/history counts do not regress after actions

## Files touched
- `frontend/src/components/IncidentDrawer.tsx`
- `e2e/tests/render-job-edge-relay.spec.ts`

## New selectors
- `incident-actor-input`
- `incident-assignee-input`
- `incident-action-reason-input`
- `incident-action-ack`
- `incident-action-assign`
- `incident-action-mute`
- `incident-action-resolve`
- `incident-action-reopen`
- `incident-current-status`
- `incident-history-item-acknowledge`
- `incident-history-item-assign`
- `incident-history-item-mute`
- `incident-history-item-resolve`
- `incident-history-item-reopen`

## Local run
```bash
make e2e-local
```

Or just the Playwright suite:
```bash
cd e2e
npm ci
npx playwright test
```
