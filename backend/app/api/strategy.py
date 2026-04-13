from __future__ import annotations

from fastapi import APIRouter

from app.schemas.strategy import StrategyModeWrite, StrategySignalRead, StrategySignalWrite, StrategyStateRead
from app.state import strategy_service

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


@router.get("/state", response_model=StrategyStateRead)
def get_strategy_state():
    return strategy_service.get_state()


@router.post("/signals", response_model=StrategySignalRead)
def create_strategy_signal(payload: StrategySignalWrite):
    return strategy_service.ingest_signal(payload.model_dump())


@router.get("/objectives")
def get_strategy_objectives():
    return strategy_service.get_objectives()


@router.get("/directives")
def get_strategy_directives():
    return {"items": strategy_service.get_directives()}


@router.get("/portfolio")
def get_strategy_portfolio():
    return strategy_service.get_portfolio()


@router.get("/sla-risk")
def get_strategy_sla_risk():
    return strategy_service.get_sla_risk()


@router.get("/business-outcomes")
def get_business_outcomes():
    return {"items": strategy_service.get_business_outcomes()}


@router.post("/modes")
def activate_strategy_mode(payload: StrategyModeWrite):
    return strategy_service.activate_mode(payload.mode, ttl_minutes=payload.ttl_minutes, note=payload.note)
