# -*- coding: utf-8 -*-
"""
FastAPI Main Application
Contract AI System Backend Server
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Configure logging
logger.remove()
# Default request_id ("-") для логов вне HTTP-контекста (startup, background tasks)
logger.configure(extra={"request_id": "-"})
_is_production = os.getenv("APP_ENV") == "production"
if _is_production:
    # JSON format for machine parsing in production (ELK, CloudWatch, etc.)
    logger.add(sys.stdout, serialize=True, level="INFO")
else:
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <magenta>rid={extra[request_id]}</magenta> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )
logger.add(
    "logs/api.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | rid={extra[request_id]} | {name}:{function}:{line} - {message}",
)

# Import settings
from config.settings import settings
from src.services.redis_runtime import ensure_local_redis

# Import database
from src.models.database import engine, Base, SessionLocal, ScopedSession

# Import middleware
from src.middleware.security import setup_security_middleware
from src.middleware.request_id import request_id_middleware

# Import routers
from src.api.auth.routes import router as auth_router
from src.api.contracts import router as contracts_router
from src.api.websocket import router as websocket_router
from src.api.payments import router as payments_router
from src.api.contracts.digital_routes import router as digital_router
from src.api.clauses import router as clauses_router
from src.api.conditions import router as conditions_router
from src.api.counterparties import router as counterparties_router
from src.api.analytics.routes import router as analytics_router
from src.api.ml import router as ml_router
from src.api.bridge import router as bridge_router
from src.api.rag_admin import router as rag_admin_router
from src.api.revisions import router as revisions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 Starting Contract AI System Backend...")
    ensure_local_redis()

    # Create tables (dev/testing only — in production use `alembic upgrade head`)
    if settings.app_env in ("development", "testing"):
        logger.info("📊 Creating database tables (dev mode)...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Error creating database tables: {e}")
    else:
        logger.info("📊 Skipping create_all in production — use alembic migrations")

    # Initialize core services (Phase 0-12)
    logger.info("🔧 Initializing core services...")
    try:
        from src.core.bootstrap import bootstrap

        # ScopedSession is a thread-local proxy: each thread gets its own
        # Session instance.  Core services store self.db = ScopedSession,
        # and every attribute access is delegated to the current thread's
        # session — safe under FastAPI's sync threadpool.
        try:
            core_services = bootstrap(ScopedSession)
            app.state.core_services = core_services
            # Persist bootstrap seed (e.g. ai_action_policies): seed_defaults()
            # лишь flush() в открытую транзакцию, а remove() без commit откатывал
            # её → таблица политик всегда оставалась пустой (фолбэк на хардкод).
            ScopedSession.commit()
            # Expire cached ORM objects after bootstrap seed.
            ScopedSession.expire_all()
            ScopedSession.remove()  # release startup session back to pool
            logger.info("✅ Core services bootstrapped successfully")
        except Exception as e:
            logger.warning(f"⚠️ Core services bootstrap skipped: {e}")
            app.state.core_services = None
            ScopedSession.remove()
    except Exception as e:
        logger.warning(f"⚠️ Core services import failed: {e}")
        app.state.core_services = None

    # Background task: periodic WebSocket stale connection cleanup
    async def _ws_cleanup_loop():
        from src.api.websocket.routes import manager as ws_manager
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            try:
                await ws_manager.cleanup_stale()
            except Exception as e:
                logger.warning(f"WS cleanup error: {e}")

    cleanup_task = asyncio.create_task(_ws_cleanup_loop())

    yield

    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    # Close all active WebSocket connections gracefully
    try:
        from src.api.websocket.routes import manager as ws_manager
        for contract_id, sockets in list(ws_manager.active_connections.items()):
            for ws in list(sockets):
                try:
                    await ws.close(code=1001, reason="Server shutdown")
                except Exception:
                    pass
    except Exception:
        pass
    ScopedSession.remove()
    logger.info("👋 Shutting down Contract AI System Backend...")


# Create FastAPI app — disable docs in production
_is_debug = getattr(settings, "debug", False)
app = FastAPI(
    title="Contract AI System API",
    description="Backend API for Contract AI System with authentication, contract analysis, and document generation",
    version="1.0.0",
    docs_url="/api/docs" if _is_debug else None,
    redoc_url="/api/redoc" if _is_debug else None,
    openapi_url="/api/openapi.json" if _is_debug else None,
    lifespan=lifespan,
)

# Local Redis should be available before rate-limiting middleware initializes.
ensure_local_redis()

# Security middleware setup (includes CORS, rate limiting, security headers)
setup_security_middleware(app)

# Request ID middleware — propagates X-Request-Id через loguru-контекст и response headers
app.middleware("http")(request_id_middleware)

# Prometheus metrics — GET /metrics (HTTP latency/requests + custom LLM metrics)
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    logger.info("📈 Prometheus metrics mounted at /metrics")
except ImportError:
    logger.warning("⚠️ prometheus-fastapi-instrumentator не установлен — /metrics недоступен")


# ScopedSession is thread-local — safe for core services that run in uvicorn's
# sync threadpool (via run_in_executor). It is NOT used in async endpoint handlers
# directly; those always use Depends(get_db) → plain SessionLocal per-request.
# .remove() here cleans up any thread-local session that sync core service code
# may have opened during the request, preventing session leaks across requests.
@app.middleware("http")
async def cleanup_scoped_session(request: Request, call_next):
    response = await call_next(request)
    ScopedSession.remove()
    return response


# Exception handlers — unified {error, message, details} format

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with unified format"""
    if isinstance(exc.detail, str):
        error = exc.detail
        message = exc.detail
        details = None
    elif isinstance(exc.detail, dict):
        error = exc.detail.get("error", "Request error")
        message = exc.detail.get("message", error)
        details = exc.detail.get("details")
    else:
        error = "Request error"
        message = str(exc.detail)
        details = exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error, "message": message, "details": details},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with unified format"""
    errors = exc.errors()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "message": f"{len(errors)} validation error(s)",
            "details": [
                {
                    "field": " -> ".join(str(loc) for loc in e.get("loc", [])),
                    "message": e.get("msg", ""),
                    "type": e.get("type", ""),
                }
                for e in errors
            ],
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
            "details": None,
        }
    )


# Health check
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint — verifies DB and Redis connectivity."""
    checks = {}

    # Check PostgreSQL
    try:
        db = SessionLocal()
        from sqlalchemy import text as sa_text
        db.execute(sa_text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"

    # Check Redis
    try:
        ensure_local_redis()
        import redis
        r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "version": "1.0.0",
        "service": "Contract AI System API",
        "checks": checks,
    }


# API info
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information"""
    return {
        "name": "Contract AI System API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }


# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(contracts_router, prefix="/api/v1/contracts", tags=["Contracts"])
app.include_router(digital_router, prefix="/api/v1/contracts", tags=["Digital Verification"])
app.include_router(websocket_router, prefix="/api/v1/ws", tags=["WebSocket"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(clauses_router, prefix="/api/v1/clauses", tags=["Clause Library"])
app.include_router(conditions_router, prefix="/api/v1/conditions", tags=["Company Conditions"])
app.include_router(counterparties_router, prefix="/api/v1/counterparties", tags=["Counterparties"])
app.include_router(rag_admin_router, prefix="/api/v1/rag", tags=["RAG Admin"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(ml_router, prefix="/api/v1/ml", tags=["ML & AI"])
app.include_router(bridge_router, prefix="/api/v1/bridge", tags=["Bridge Integration"])
app.include_router(revisions_router, prefix="/api/v1/revisions", tags=["Revisions"])

# API v2 — AI-collaborative OS
from src.api.v2.router import v2_router
app.include_router(v2_router, prefix="/api/v2", tags=["API v2"])


# NOTE: Static files for contracts are NOT mounted publicly.
# Use the authenticated /api/v1/contracts/{id}/download endpoint instead.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
