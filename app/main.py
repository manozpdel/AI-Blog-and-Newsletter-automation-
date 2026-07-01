from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.page_routes import page_router
from app.api.routes import router as api_router
from app.core.logging import RequestLoggingMiddleware
from app.db.base import Base
from app.db.session import async_engine

# Explicit model imports so all tables are registered before create_all
import app.models.models      # noqa: F401
import app.models.newsletter  # noqa: F401
import app.models.subscriber  # noqa: F401
import app.models.email_log   # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="AI Blog + Newsletter Automation Platform",
    description="AI Content Automation backend powered by FastAPI, LangChain and Groq",
    version="0.6.0",
    lifespan=lifespan,
    # Keep docs accessible for API testing
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Structured request logging
app.add_middleware(RequestLoggingMiddleware)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# HTML page routes (no schema, served as HTML)
app.include_router(page_router)

# REST API routes
app.include_router(api_router)