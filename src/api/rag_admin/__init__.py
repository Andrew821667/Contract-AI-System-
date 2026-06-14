# -*- coding: utf-8 -*-
from .routes import router
from . import update_routes  # noqa: F401 — регистрирует /update/* эндпоинты на router
