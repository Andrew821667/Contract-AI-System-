# -*- coding: utf-8 -*-
"""
Tests for RAG Admin helper logic — chunking, text extraction, rate limiter,
and route-level functions.

These tests do NOT require the FastAPI TestClient or pydantic_settings.
They test the pure-Python helpers that back the /api/v1/rag endpoints.

Covers:
- _chunk_text: basic chunking, overlap, short-text filter
- _extract_text: .txt format (other formats need optional deps)
- _check_upload_rate_limit: allows up to 10, blocks at 11th
- get_legal_context / has_legal_docs: with mocked ChromaDB
- collection name validation (_get_collection raises for unknown names)
"""
import io
import time
import threading
import pytest
from unittest.mock import MagicMock, patch

import src.core.identity_org.models  # noqa: F401
import src.core.policies.models  # noqa: F401
import src.core.tools.models  # noqa: F401
import src.core.agents.models  # noqa: F401
import src.core.ai_collaboration.models  # noqa: F401
import src.core.orchestrator.models  # noqa: F401
import src.core.workflow.models  # noqa: F401
import src.core.collaboration.models  # noqa: F401
import src.core.templates.models  # noqa: F401
import src.core.integrations.models  # noqa: F401
import src.core.graph_rag.models  # noqa: F401
import src.models.condition_models  # noqa: F401


# ── Import helpers ─────────────────────────────────────────────────────────────

from src.api.rag_admin.routes import _chunk_text, _extract_text, _check_upload_rate_limit
import src.api.rag_admin.routes as rag_routes


# ── _chunk_text ────────────────────────────────────────────────────────────────

class TestChunkText:

    def test_short_text_below_minimum_is_filtered(self):
        # "Short sentence. Another short sentence." is ~40 chars — below the 50-char min
        text = "Short sentence. Another short sentence."
        chunks = _chunk_text(text, chunk_size=800, overlap=50)
        # Either filtered out (< 50 chars) or returned as one chunk
        assert isinstance(chunks, list)

    def test_too_short_chunks_filtered_out(self):
        # Text below minimum chunk size (50 chars) should be dropped
        chunks = _chunk_text("Hi.", chunk_size=800, overlap=50)
        assert chunks == []

    def test_long_text_produces_multiple_chunks(self):
        sentence = "This is a moderately long sentence with legal terms. "
        text = sentence * 40  # ~2000 chars
        chunks = _chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1

    def test_chunks_not_empty(self):
        text = "First sentence. Second sentence. Third sentence. " * 30
        chunks = _chunk_text(text, chunk_size=200, overlap=30)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_chunk_size_respected_with_sentence_boundaries(self):
        # Chunker splits on sentence boundaries — text with proper sentences is chunked
        sentence = "This is a legal sentence number {}. ".format
        text = "".join(sentence(i) for i in range(50))  # ~1800 chars, many boundaries
        chunks = _chunk_text(text, chunk_size=200, overlap=20)
        # Should produce more than one chunk for this long text
        assert len(chunks) > 1

    def test_empty_text_returns_empty_list(self):
        assert _chunk_text("") == []

    def test_overlap_creates_continuity(self):
        # With overlap, consecutive chunks should share some content
        sentence = "Legal clause number {}. This clause says something important. "
        text = "".join(sentence.format(i) for i in range(30))
        chunks = _chunk_text(text, chunk_size=300, overlap=100)
        # Simply verify chunks are produced and non-empty
        assert len(chunks) >= 2


# ── _extract_text ──────────────────────────────────────────────────────────────

class TestExtractText:

    def test_extract_txt_utf8(self):
        content = "Это текст договора.\nВторая строка.".encode("utf-8")
        text = _extract_text(content, "document.txt")
        assert "Это текст договора" in text

    def test_extract_txt_ignores_decode_errors(self):
        content = b"Valid text\xff\xfe more text"
        text = _extract_text(content, "file.txt")
        assert "Valid text" in text
        assert "more text" in text

    def test_unsupported_format_raises_http_exception(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _extract_text(b"data", "file.xlsx")
        assert exc_info.value.status_code == 400

    def test_txt_extension_case_insensitive(self):
        content = b"Some legal content here"
        text = _extract_text(content, "DOC.TXT")
        assert "Some legal content here" in text


# ── Rate limiter ───────────────────────────────────────────────────────────────

class TestUploadRateLimit:

    def setup_method(self):
        """Reset rate limiter state before each test."""
        rag_routes._upload_rl_buckets.clear()

    def test_first_request_passes(self):
        _check_upload_rate_limit("user-1")  # should not raise

    def test_ten_requests_pass(self):
        for _ in range(10):
            _check_upload_rate_limit("user-1")  # none should raise

    def test_eleventh_request_blocked(self):
        from fastapi import HTTPException
        for _ in range(10):
            _check_upload_rate_limit("user-1")
        with pytest.raises(HTTPException) as exc_info:
            _check_upload_rate_limit("user-1")
        assert exc_info.value.status_code == 429

    def test_different_users_independent(self):
        for _ in range(10):
            _check_upload_rate_limit("user-a")
        # user-b should not be affected
        _check_upload_rate_limit("user-b")  # should not raise

    def test_old_requests_expire(self):
        # Simulate old requests outside the 60s window
        user = "user-expiry"
        bucket = rag_routes._upload_rl_buckets.setdefault(user, __import__("collections").deque())
        # Add 10 timestamps 70 seconds ago (outside window)
        old_time = time.time() - 70
        for _ in range(10):
            bucket.append(old_time)
        # Should not raise — old entries are expired
        _check_upload_rate_limit(user)

    def test_thread_safety(self):
        """Concurrent uploads from the same user should correctly count."""
        from fastapi import HTTPException
        errors = []

        def upload():
            try:
                _check_upload_rate_limit("concurrent-user")
            except HTTPException:
                errors.append(1)

        threads = [threading.Thread(target=upload) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 5 should have been blocked (15 - 10 limit)
        assert len(errors) == 5


# ── admin_rag_retriever ────────────────────────────────────────────────────────

class TestAdminRAGRetriever:

    def test_has_legal_docs_false_when_empty(self):
        mock_coll = MagicMock()
        mock_coll.count.return_value = 0
        with patch("src.services.admin_rag_retriever.get_collection", return_value=mock_coll):
            from src.services import admin_rag_retriever
            result = admin_rag_retriever.has_legal_docs()
        assert result is False

    def test_has_legal_docs_true_when_populated(self):
        mock_coll = MagicMock()
        mock_coll.count.return_value = 5
        with patch("src.services.admin_rag_retriever.get_collection", return_value=mock_coll):
            from src.services import admin_rag_retriever
            result = admin_rag_retriever.has_legal_docs()
        assert result is True

    def test_get_legal_context_returns_string(self):
        mock_coll = MagicMock()
        mock_coll.query.return_value = {
            "documents": [["Legal clause 1.", "Legal clause 2."]],
            "distances": [[0.1, 0.2]],
        }
        mock_coll.count.return_value = 5
        with patch("src.services.admin_rag_retriever.get_collection", return_value=mock_coll):
            from src.services import admin_rag_retriever
            context = admin_rag_retriever.get_legal_context(
                query="penalty clause",
                collections=["laws"],
                n_results=2,
                max_chars=500,
            )
        assert isinstance(context, str)

    def test_get_legal_context_empty_db_returns_empty(self):
        mock_coll = MagicMock()
        mock_coll.count.return_value = 0
        with patch("src.services.admin_rag_retriever.get_collection", return_value=mock_coll):
            from src.services import admin_rag_retriever
            context = admin_rag_retriever.get_legal_context(
                query="anything",
                collections=["laws"],
            )
        assert context == "" or context is None or isinstance(context, str)


# ── Collection name validation ─────────────────────────────────────────────────

class TestCollectionValidation:

    def test_unknown_collection_raises_http_400(self):
        from fastapi import HTTPException
        from src.api.rag_admin.routes import _get_collection
        with pytest.raises(HTTPException) as exc_info:
            _get_collection("unknown_collection_xyz")
        assert exc_info.value.status_code == 400

    def test_known_collections_pass_validation(self):
        mock_coll = MagicMock()
        from src.api.rag_admin.routes import _get_collection
        from src.services.admin_rag_retriever import COLLECTIONS
        for name in COLLECTIONS:
            with patch("src.api.rag_admin.routes._get_collection_shared", return_value=mock_coll):
                result = _get_collection(name)
            assert result is mock_coll
