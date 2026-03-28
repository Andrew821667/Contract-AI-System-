# -*- coding: utf-8 -*-
"""
Root conftest — runs before any test module is imported.

Sets DATABASE_URL to SQLite so that tests don't require PostgreSQL.
The application itself uses PostgreSQL only.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fallback.db")
