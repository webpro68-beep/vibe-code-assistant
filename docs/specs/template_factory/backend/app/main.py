from fastapi import FastAPI
from app.api.v1.templates import router as templates_router

app = FastAPI(title="Template Factory Layer")
app.include_router(templates_router, prefix="/api/v1")
