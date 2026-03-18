# -*- coding: utf-8 -*-
"""
Contract Operations API Routes — Aggregator

Combines all sub-routers into a single router for backward compatibility.
"""
from fastapi import APIRouter

# Re-export for backward compatibility (other modules import this from here)
from src.api.dependencies import get_current_user  # noqa: F401

from .upload_routes import router as upload_router
from .analysis_routes import router as analysis_router
from .generation_routes import router as generation_router
from .export_routes import router as export_router
from .listing_routes import router as listing_router
from .version_routes import router as version_router


router = APIRouter()

router.include_router(upload_router)
router.include_router(analysis_router)
router.include_router(generation_router)
router.include_router(export_router)
router.include_router(listing_router)
router.include_router(version_router)
