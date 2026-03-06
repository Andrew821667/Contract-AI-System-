# -*- coding: utf-8 -*-
"""
FastAPI Main Application
Contract AI System Backend Server
"""
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
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)
logger.add(
    "logs/api.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

# Import settings
from config.settings import settings

# Import database
from src.models.database import engine, Base, SessionLocal

# Import middleware
from src.middleware.security import setup_security_middleware

# Import routers
from src.api.auth.routes import router as auth_router
from src.api.contracts import router as contracts_router
from src.api.websocket import router as websocket_router
from src.api.payments import router as payments_router
from src.api.contracts.digital_routes import router as digital_router
from src.api.clauses import router as clauses_router
from src.api.analytics.routes import router as analytics_router
from src.api.ml import router as ml_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 Starting Contract AI System Backend...")

    # Create tables
    logger.info("📊 Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")

    # Initialize services
    logger.info("🔧 Initializing services...")

    yield

    # Shutdown
    logger.info("👋 Shutting down Contract AI System Backend...")


# Create FastAPI app
app = FastAPI(
    title="Contract AI System API",
    description="Backend API for Contract AI System with authentication, contract analysis, and document generation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Security middleware setup (includes CORS, rate limiting, security headers)
setup_security_middleware(app)


# Exception handlers — unified {error, message, details} format

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with unified format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "Request error",
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": None,
        }
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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "Contract AI System API"
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
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(ml_router, prefix="/api/v1/ml", tags=["ML & AI"])


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
