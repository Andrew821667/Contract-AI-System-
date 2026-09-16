# -*- coding: utf-8 -*-
"""Единый формат ошибок не должен терять структурные детали HTTPException.

Найдено в сквозном прогоне демо: запуск анализа отвечал 409
analysis_perspective_required со списком сторон, а единый обработчик
оставлял только {error, message, details} — фронт не находил `detail.code`
и вместо выбора стороны показывал тост с текстом ошибки.
"""
from fastapi import HTTPException

from src.main import app, http_exception_handler


class TestHttpExceptionFormat:
    def test_dict_detail_keeps_code_and_extra_keys(self):
        import asyncio

        exc = HTTPException(
            status_code=409,
            detail={
                "code": "analysis_perspective_required",
                "message": "Укажите сторону",
                "parties": ["Поставщик", "Покупатель"],
            },
        )
        response = asyncio.run(http_exception_handler(None, exc))
        import json

        body = json.loads(response.body)
        assert response.status_code == 409
        assert body["message"] == "Укажите сторону"
        assert body["code"] == "analysis_perspective_required"
        assert body["detail"]["code"] == "analysis_perspective_required"
        assert body["detail"]["parties"] == ["Поставщик", "Покупатель"]

    def test_string_detail_is_also_exposed_as_detail(self):
        import asyncio
        import json

        response = asyncio.run(http_exception_handler(None, HTTPException(status_code=404, detail="Не найдено")))
        body = json.loads(response.body)
        assert body == {"error": "Не найдено", "message": "Не найдено", "details": None, "detail": "Не найдено"}
        assert app is not None
