# -*- coding: utf-8 -*-
"""
Conftest для graph_rag тестов.

Standalone: не зависит от FastAPI app, работает с чистым SQLAlchemy.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base

# Регистрируем модели в Base.metadata
import src.core.graph_rag.models  # noqa


@pytest.fixture()
def test_db(tmp_path):
    """Чистая SQLite БД для каждого теста."""
    db_path = str(tmp_path / "test_graph_rag.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
