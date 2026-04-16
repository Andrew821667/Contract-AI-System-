# -*- coding: utf-8 -*-
"""
Request ID middleware — propagate X-Request-Id через весь lifecycle запроса.

- Принимает X-Request-Id из заголовка (или генерирует UUID4).
- Кладёт в request.state.request_id и в loguru-контекст (через contextualize).
- Возвращает в ответе как X-Request-Id.
"""
from __future__ import annotations

import uuid

from fastapi import Request
from loguru import logger


async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id")
    request_id = incoming if incoming else uuid.uuid4().hex
    request.state.request_id = request_id
    with logger.contextualize(request_id=request_id):
        response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response
