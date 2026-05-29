# -*- coding: utf-8 -*-
"""
Revision compare API — produces a side-by-side report for two contract
revisions in JSON / xlsx / PDF, all driven by the same underlying
`RevisionComparator`.

Endpoints (mounted at `/api/v1/revisions` in main.py):

  POST  /compare        body: CompareRequest, query: ?format=json|xlsx|pdf
                        - json → application/json with the full report
                          (rows + summary). Used by the UI to render the
                          comparison table in-app.
                        - xlsx → file download (template-matched workbook).
                        - pdf  → file download (landscape A3, same look).

  GET   /{contract_id}  list available revisions of the given contract
                        — used by the UI dropdown «Сравнить с …».

JSON, xlsx, and PDF share the *exact same* data so what the lawyer
sees in the UI is byte-equivalent to what they download.
"""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.changes_models import ContractVersion
from src.models.database import get_db
from src.services.document_diff_service import DocumentDiffService
from src.services.document_parser import DocumentParser
from src.services.llm_gateway import LLMGateway
from src.services.revision_comparator import (
    Perspective,
    RevisionComparator,
    RevisionDiffReport,
)
from src.services.revision_pdf_exporter import export_report as pdf_export_report
from src.services.revision_xlsx_exporter import export_report as xlsx_export_report


class _ParserAdapter:
    """Adapt DocumentParser to the interface RevisionComparator expects.

    Comparator wants `extract_clauses(content) -> list[{number, title, text}]`.

    DocumentParser.parse() returns XML (it wraps every supported format —
    txt, pdf, docx — in a `<contract>...<clauses><clause>...` envelope),
    so we parse that XML and pull clause titles + paragraphs directly.
    A leading "1.2.3" in the title becomes `number`.

    If the content is *not* XML (defensive fallback — e.g. some caller
    passes raw text in the future), we fall back to
    `_extract_sections_from_text` which scans for numbered headings.
    """

    _NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)")

    def __init__(self, inner: DocumentParser) -> None:
        self._inner = inner

    def parse(self, path: str) -> str:
        return self._inner.parse(path)

    # Wider heading regex than DocumentParser._is_section_heading_text:
    # matches both "1. Предмет договора" and "1.1 Предмет договора" /
    # "2.3 Оплата" (multi-level numbering common in contracts).
    _HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")

    def extract_clauses(self, content: str) -> list[dict[str, Any]]:
        sections = self._sections_from_xml(content)
        if sections is None:
            sections = self._inner._extract_sections_from_text(content)

        # If the parser produced a single "Преамбула" blob (its heading
        # regex doesn't catch multi-level numbering like "1.1", "2.3"),
        # rescan the flattened paragraphs ourselves with a wider regex.
        if len(sections) <= 1:
            flat: list[str] = []
            for s in sections:
                flat.extend(s.get("paragraphs", []) or [])
            rescanned = self._sections_from_lines(flat)
            if len(rescanned) > len(sections):
                sections = rescanned

        out: list[dict[str, Any]] = []
        for s in sections:
            title = (s.get("title") or "").strip()
            m = self._NUMBER_RE.match(title)
            number = m.group(1) if m else None
            text = "\n".join(s.get("paragraphs", []) or []).strip()
            if number is None and not text:
                continue
            out.append({"number": number, "title": title, "text": text})
        return out

    @classmethod
    def _sections_from_lines(cls, lines: list[str]) -> list[dict[str, Any]]:
        """Walk a flat list of lines and start a new section whenever a
        line matches the wider numbered-heading regex."""
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw in lines:
            line = (raw or "").strip()
            if not line:
                continue
            m = cls._HEADING_RE.match(line)
            if m:
                if current is not None:
                    sections.append(current)
                current = {"title": line, "type": "general", "paragraphs": []}
            else:
                if current is None:
                    current = {"title": "Преамбула", "type": "preamble", "paragraphs": []}
                current["paragraphs"].append(line)
        if current is not None:
            sections.append(current)
        return sections

    @staticmethod
    def _sections_from_xml(content: str) -> list[dict[str, Any]] | None:
        """Return clause sections parsed from the parser's XML envelope.

        Returns None if `content` doesn't look like the parser's XML output.
        """
        head = content.lstrip()[:200]
        if not head.startswith("<?xml") and "<contract" not in head:
            return None

        # Local import — lxml is already a project dep via DocumentParser.
        try:
            from lxml import etree
        except ImportError:
            return None

        try:
            root = etree.fromstring(content.encode("utf-8"))
        except (etree.XMLSyntaxError, ValueError):
            return None

        sections: list[dict[str, Any]] = []
        for clause in root.iterfind(".//clauses/clause"):
            title_el = clause.find("title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            paragraphs = [
                (p.text or "").strip()
                for p in clause.iterfind(".//paragraph")
                if (p.text or "").strip()
            ]
            sections.append({
                "title": title,
                "type": clause.get("type", "general"),
                "paragraphs": paragraphs,
            })
        return sections


router = APIRouter()


# ---------- request / response schemas ------------------------------------

class CompareRequest(BaseModel):
    """Payload for POST /compare."""

    old_revision_id: int = Field(..., description="ID более ранней редакции")
    new_revision_id: int = Field(..., description="ID более поздней редакции")
    perspective: Perspective = Field(
        Perspective.NEUTRAL,
        description="С чьей точки зрения оценивать изменения",
    )
    title: Optional[str] = Field(
        None,
        description="Заголовок отчёта; если не задан — берётся имя файла новой редакции",
    )


class RevisionListItem(BaseModel):
    id: int
    version_number: int
    source: str
    description: Optional[str]
    is_current: bool
    file_name: str
    uploaded_at: Optional[str]


# ---------- helpers --------------------------------------------------------

def _load_revision(db: Session, revision_id: int) -> ContractVersion:
    rev = db.query(ContractVersion).filter(ContractVersion.id == revision_id).first()
    if rev is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ContractVersion {revision_id} not found",
        )
    return rev


def _read_content(version: ContractVersion, parser: _ParserAdapter) -> str:
    """Return parsed text content of the revision's file.

    Errors out with 422 if the file isn't readable — keeps the endpoint
    from silently producing an empty report.
    """
    file_path = Path(version.file_path or "")
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ContractVersion {version.id} file is missing on disk",
        )
    try:
        return parser.parse(str(file_path))   # returns plain text
    except Exception as exc:
        logger.exception("Failed to parse revision %s file", version.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse revision {version.id}: {exc}",
        )


def _label_for(version: ContractVersion) -> str:
    return f"Редакция №{version.version_number}"


def _file_name(version: ContractVersion) -> str:
    return Path(version.file_path or "").name or _label_for(version)


def _build_report(
    db: Session,
    req: CompareRequest,
) -> tuple[RevisionDiffReport, str, str]:
    """Load revisions, run the comparator, return (report, old_label, new_label)."""
    old = _load_revision(db, req.old_revision_id)
    new = _load_revision(db, req.new_revision_id)
    if old.id == new.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="old_revision_id and new_revision_id must differ",
        )

    parser = _ParserAdapter(DocumentParser())
    old_content = _read_content(old, parser)
    new_content = _read_content(new, parser)

    old_label = _label_for(old)
    new_label = _label_for(new)

    comparator = RevisionComparator(
        diff_service=DocumentDiffService(),
        llm_gateway=LLMGateway(),
        parser=parser,
        old_revision_label=old_label,
        new_revision_label=new_label,
    )

    report = comparator.compare(
        old_content,
        new_content,
        perspective=req.perspective,
        title=req.title or f"Сравнение редакций договора (v{old.version_number} → v{new.version_number})",
        old_file_name=_file_name(old),
        new_file_name=_file_name(new),
    )
    return report, old_label, new_label


def _tmp_path(suffix: str) -> Path:
    """Per-request temp file path, cleaned up by the OS."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix=f"revision_compare_{uuid.uuid4().hex[:8]}_", suffix=suffix)
    import os
    os.close(fd)
    return Path(path)


# ---------- endpoints -----------------------------------------------------

@router.post(
    "/compare",
    summary="Сравнить две редакции договора (JSON / xlsx / PDF)",
    responses={
        200: {"description": "Сравнение, в формате `format`"},
        400: {"description": "Запрос некорректен"},
        404: {"description": "Одна из редакций не найдена"},
        422: {"description": "Файл редакции недоступен или не парсится"},
    },
)
def compare_revisions(
    req: CompareRequest,
    format: Literal["json", "xlsx", "pdf"] = Query("json"),
    db: Session = Depends(get_db),
) -> Any:
    report, old_label, new_label = _build_report(db, req)

    if format == "json":
        return JSONResponse(report.as_dict())

    if format == "xlsx":
        out = _tmp_path(".xlsx")
        xlsx_export_report(report, out, old_revision_label=old_label, new_revision_label=new_label)
        buffer = io.BytesIO(out.read_bytes())
        out.unlink(missing_ok=True)
        filename = f"revision_compare_v{req.old_revision_id}_v{req.new_revision_id}.xlsx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "pdf":
        out = _tmp_path(".pdf")
        pdf_export_report(report, out, old_revision_label=old_label, new_revision_label=new_label)
        buffer = io.BytesIO(out.read_bytes())
        out.unlink(missing_ok=True)
        filename = f"revision_compare_v{req.old_revision_id}_v{req.new_revision_id}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown format: {format}",
    )


@router.get(
    "/{contract_id}",
    summary="Список редакций договора (для dropdown «сравнить с …»)",
    response_model=list[RevisionListItem],
)
def list_revisions(contract_id: str, db: Session = Depends(get_db)) -> list[RevisionListItem]:
    rows = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number.asc())
        .all()
    )
    return [
        RevisionListItem(
            id=r.id,
            version_number=r.version_number,
            source=r.source or "unknown",
            description=r.description,
            is_current=bool(r.is_current),
            file_name=Path(r.file_path or "").name,
            uploaded_at=r.uploaded_at.isoformat() if r.uploaded_at else None,
        )
        for r in rows
    ]
