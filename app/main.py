"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reem")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_db()
    mode = "DEMO MODE" if not settings.ai_available() else "LIVE MODEL"
    logger.info("Reem starting (%s)", mode)
    yield


app = FastAPI(
    title="AI Reimbursement Employee — Reem",
    description="Conference prototype: AI understands, code decides, humans authorize.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
