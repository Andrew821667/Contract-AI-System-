# -*- coding: utf-8 -*-
"""
Contract Operations API Routes — Aggregator

Combines all sub-module routes into a single router for backward compatibility.
Import pattern: `from src.api.contracts import router` or `from src.api.contracts.routes import router`
"""
from fastapi import APIRouter

# Re-export for backward compatibility (other modules import this from here)
from src.api.dependencies import get_current_user  # noqa: F401

# Import individual route modules — they register endpoints on their own routers
from .upload_routes import router as upload_router
from .analysis_routes import router as analysis_router
from .generation_routes import router as generation_router
from .export_routes import router as export_router
from .listing_routes import router as listing_router
from .version_routes import router as version_router
from .admin_routes import router as admin_router
from .template_routes import router as template_router
from .relations_routes import router as relations_router


# Build combined router by including sub-routers
# Note: sub-routers with path="" endpoints need prefix="/" workaround
router = APIRouter()

# Routes with non-empty paths can be included directly
router.include_router(upload_router)
router.include_router(analysis_router)
router.include_router(generation_router)
router.include_router(export_router)
router.include_router(version_router)
router.include_router(admin_router)
router.include_router(template_router)
router.include_router(relations_router)

# listing_router has a GET "" endpoint — register its routes directly
for route in listing_router.routes:
    router.routes.append(route)
