from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import answers, audio, auth, evaluations, interviews, jobs, resumes


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan hooks for startup and shutdown logging."""

    logger.info("Starting MockWithUs API in %s mode.", settings.environment)
    yield
    logger.info("Shutting down MockWithUs API.")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(interviews.router)
app.include_router(answers.router)
app.include_router(evaluations.router)
app.include_router(audio.router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a simple process health status."""

    return {"status": "ok", "service": "mockwithus-backend"}
