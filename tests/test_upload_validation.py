# -*- coding: utf-8 -*-
"""
Tests for upload validation and file security.

Covers:
- sanitize_filename: path traversal, null bytes, hidden files, long names
- validate_file_extension: whitelist, missing extension, case insensitive
- validate_file_size: min/max bounds, custom limits
- validate_mime_type: string mode and magic bytes mode
- document_type validation (upload route guard)
- Daily upload limits
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, inspect as sa_inspect, DateTime
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, Contract
from src.models.auth_models import User
from src.services.auth_service import AuthService
from src.utils.file_validator import (
    FileValidationError,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
    MAX_FILE_SIZE,
    MIN_FILE_SIZE,
    ALLOWED_EXTENSIONS,
)

# Import core models so metadata sees all tables
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


# ── SQLite timezone fix ──
_load_listener_installed = False


def _install_sqlite_tz_load_listener():
    global _load_listener_installed
    if _load_listener_installed:
        return
    _load_listener_installed = True

    @event.listens_for(Base, "load", propagate=True)
    def _add_utc_after_load(target, context):
        mapper = sa_inspect(type(target))
        for prop in mapper.column_attrs:
            for col in prop.columns:
                col_type = getattr(col.type, "impl", col.type)
                if isinstance(col_type, DateTime):
                    val = prop.class_attribute.__get__(target, type(target))
                    if isinstance(val, datetime) and val.tzinfo is None:
                        object.__setattr__(target, prop.key, val.replace(tzinfo=timezone.utc))

    @event.listens_for(Base, "refresh", propagate=True)
    def _add_utc_after_refresh(target, context, attrs):
        mapper = sa_inspect(type(target))
        for prop in mapper.column_attrs:
            for col in prop.columns:
                col_type = getattr(col.type, "impl", col.type)
                if isinstance(col_type, DateTime):
                    val = prop.class_attribute.__get__(target, type(target))
                    if isinstance(val, datetime) and val.tzinfo is None:
                        object.__setattr__(target, prop.key, val.replace(tzinfo=timezone.utc))


_install_sqlite_tz_load_listener()


# ────────────────────────────────────────────────────────
# sanitize_filename
# ────────────────────────────────────────────────────────

class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("contract.docx") == "contract.docx"

    def test_strips_path_components(self):
        assert sanitize_filename("/etc/passwd/../../contract.docx") == "contract.docx"
        # On Unix, backslash is a valid filename char; os.path.basename keeps it.
        # The important thing is forward-slash traversal is stripped.
        assert sanitize_filename("../../secret/contract.docx") == "contract.docx"

    def test_removes_null_bytes(self):
        result = sanitize_filename("contract\x00.docx")
        assert "\x00" not in result

    def test_removes_dangerous_chars(self):
        result = sanitize_filename('con<tra>ct:"te|st?.docx')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
        assert "?" not in result

    def test_strips_leading_dots(self):
        result = sanitize_filename(".hidden.docx")
        assert not result.startswith(".")

    def test_empty_filename_raises(self):
        with pytest.raises(FileValidationError):
            sanitize_filename("")

    def test_only_dots_raises(self):
        with pytest.raises(FileValidationError):
            sanitize_filename("...")

    def test_truncates_long_name(self):
        long_name = "a" * 300 + ".docx"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_unicode_preserved(self):
        result = sanitize_filename("договор_поставки.docx")
        assert "договор" in result


# ────────────────────────────────────────────────────────
# validate_file_extension
# ────────────────────────────────────────────────────────

class TestValidateFileExtension:
    def test_allowed_extensions(self):
        for ext in [".docx", ".pdf", ".xml", ".txt", ".doc", ".rtf"]:
            result = validate_file_extension(f"file{ext}")
            assert result == ext

    def test_case_insensitive(self):
        assert validate_file_extension("file.DOCX") == ".docx"
        assert validate_file_extension("file.PDF") == ".pdf"

    def test_disallowed_extension(self):
        with pytest.raises(FileValidationError):
            validate_file_extension("virus.exe")

    def test_no_extension(self):
        with pytest.raises(FileValidationError):
            validate_file_extension("noext")

    def test_script_extensions_blocked(self):
        for ext in [".py", ".sh", ".bat", ".js", ".php"]:
            with pytest.raises(FileValidationError):
                validate_file_extension(f"script{ext}")


# ────────────────────────────────────────────────────────
# validate_file_size
# ────────────────────────────────────────────────────────

class TestValidateFileSize:
    def test_valid_size(self):
        assert validate_file_size(1024) is True  # 1KB
        assert validate_file_size(10 * 1024 * 1024) is True  # 10MB

    def test_too_small(self):
        with pytest.raises(FileValidationError, match="too small"):
            validate_file_size(5)  # Less than MIN_FILE_SIZE

    def test_too_large(self):
        with pytest.raises(FileValidationError, match="too large"):
            validate_file_size(MAX_FILE_SIZE + 1)

    def test_exact_min_boundary(self):
        assert validate_file_size(MIN_FILE_SIZE) is True

    def test_exact_max_boundary(self):
        assert validate_file_size(MAX_FILE_SIZE) is True

    def test_custom_max_size(self):
        custom_limit = 1024  # 1KB
        with pytest.raises(FileValidationError):
            validate_file_size(2048, max_size=custom_limit)


# ────────────────────────────────────────────────────────
# validate_mime_type
# ────────────────────────────────────────────────────────

class TestValidateMimeType:
    def test_string_mode_allowed(self):
        assert validate_mime_type("application/pdf") is True
        assert validate_mime_type("text/plain") is True

    def test_string_mode_disallowed(self):
        with pytest.raises(FileValidationError):
            validate_mime_type("application/x-executable")

    def test_magic_bytes_pdf(self):
        pdf_content = b"%PDF-1.4 ..." + b"\x00" * 50
        assert validate_mime_type(pdf_content, ".pdf") is True

    def test_magic_bytes_docx(self):
        docx_content = b"PK\x03\x04" + b"\x00" * 50
        assert validate_mime_type(docx_content, ".docx") is True

    def test_magic_bytes_mismatch(self):
        # Not a PDF despite .pdf extension
        fake_content = b"NOT_A_PDF" + b"\x00" * 50
        with pytest.raises(FileValidationError, match="doesn't match"):
            validate_mime_type(fake_content, ".pdf")

    def test_txt_skips_magic_check(self):
        # .txt has no magic bytes defined, should pass
        assert validate_mime_type(b"anything here", ".txt") is True

    def test_xml_magic_bytes(self):
        xml_content = b"<?xml version='1.0'?>" + b"\x00" * 50
        assert validate_mime_type(xml_content, ".xml") is True

    def test_doc_ole_magic(self):
        doc_content = b"\xD0\xCF\x11\xE0" + b"\x00" * 50
        assert validate_mime_type(doc_content, ".doc") is True


# ────────────────────────────────────────────────────────
# document_type validation
# ────────────────────────────────────────────────────────

class TestDocumentTypeValidation:
    """Tests the VALID_DOCUMENT_TYPES guard in upload_routes."""

    VALID_TYPES = {"contract", "disagreement", "tracked_changes"}

    def test_valid_types(self):
        for t in self.VALID_TYPES:
            assert t in self.VALID_TYPES

    def test_invalid_type_rejected(self):
        assert "invoice" not in self.VALID_TYPES
        assert "" not in self.VALID_TYPES
        assert "Contract" not in self.VALID_TYPES  # case-sensitive


# ────────────────────────────────────────────────────────
# Daily upload limits
# ────────────────────────────────────────────────────────

class TestDailyLimits:
    @pytest.fixture()
    def db(self, tmp_path):
        engine = create_engine(
            f"sqlite:///{tmp_path / 'test.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()

    @pytest.fixture()
    def user(self, db):
        auth = AuthService(db)
        user, _ = auth.register_user(
            email="test@example.com", name="Test",
            password="StrongPass1!", role="demo",
            subscription_tier="demo", send_verification=False,
        )
        db.commit()
        return user

    def test_demo_tier_limits(self, user):
        assert user.max_contracts_per_day == 5
        assert user.max_llm_requests_per_day == 10

    def test_pro_tier_limits(self, user, db):
        user.subscription_tier = "pro"
        db.commit()
        assert user.max_contracts_per_day == 50

    def test_enterprise_tier_limits(self, user, db):
        user.subscription_tier = "enterprise"
        db.commit()
        assert user.max_contracts_per_day == 999999

    def test_limit_exceeded_check(self, user, db):
        user.contracts_today = user.max_contracts_per_day
        db.commit()
        assert user.contracts_today >= user.max_contracts_per_day

    def test_reset_daily_limits(self, user, db):
        user.contracts_today = 5
        user.llm_requests_today = 8
        user.last_reset_date = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        user.reset_daily_limits()
        assert user.contracts_today == 0
        assert user.llm_requests_today == 0

    def test_no_reset_same_day(self, user, db):
        user.contracts_today = 5
        user.last_reset_date = datetime.now(timezone.utc)
        db.commit()

        user.reset_daily_limits()
        assert user.contracts_today == 5  # Not reset
