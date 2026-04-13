# Enterprise Strategy Patch — 2026-04-12

This patch adds an enterprise strategy alignment layer on top of the unified production timeline and audio pipeline.

## Added surfaces

- Strategy signals ingestion
- Objective translation engine
- Trade-off governance engine
- Portfolio allocation plan
- Directive bridge down to runtime/fabric layers
- Strategy Console frontend
- Basic workers for refresh, rollup, rebalance, business outcomes, and mode expiry

## Core endpoints

- `GET /api/v1/strategy/state`
- `POST /api/v1/strategy/signals`
- `GET /api/v1/strategy/objectives`
- `GET /api/v1/strategy/directives`
- `GET /api/v1/strategy/portfolio`
- `GET /api/v1/strategy/sla-risk`
- `GET /api/v1/strategy/business-outcomes`
- `POST /api/v1/strategy/modes`

## Notes

- Repository/storage in this patch is in-memory so the layer can be grafted into the latest monorepo safely.
- Directive bridge is normalized around priority weights, capacity reservation, quality floors, cost envelope shaping, and experiment freeze.
- Safety/compliance is treated as the highest objective in every objective stack.
