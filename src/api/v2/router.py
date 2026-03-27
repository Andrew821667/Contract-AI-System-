# -*- coding: utf-8 -*-
"""
API v2 — Общий роутер.

Объединяет все sub-routers Phase 0 под prefix /api/v2.
"""
from fastapi import APIRouter

from src.api.v2.ai_sessions import router as ai_sessions_router
from src.api.v2.ai_actions import router as ai_actions_router
from src.api.v2.orchestrator import router as orchestrator_router
from src.api.v2.organizations import router as organizations_router
from src.api.v2.policies import router as policies_router
from src.api.v2.tools_agents import router as tools_agents_router
from src.api.v2.workflow import router as workflow_router
from src.api.v2.comments import router as comments_router
from src.api.v2.negotiations import router as negotiations_router
from src.api.v2.versions import router as versions_router
from src.api.v2.integrations import router as integrations_router
from src.api.v2.templates import router as templates_router
from src.api.v2.admin_llm import router as admin_llm_router
from src.api.v2.graph import router as graph_router

v2_router = APIRouter()

v2_router.include_router(admin_llm_router)
v2_router.include_router(graph_router)
v2_router.include_router(ai_sessions_router)
v2_router.include_router(ai_actions_router)
v2_router.include_router(orchestrator_router)
v2_router.include_router(organizations_router)
v2_router.include_router(policies_router)
v2_router.include_router(tools_agents_router)
v2_router.include_router(workflow_router)
v2_router.include_router(comments_router)
v2_router.include_router(negotiations_router)
v2_router.include_router(versions_router)
v2_router.include_router(integrations_router)
v2_router.include_router(templates_router)
