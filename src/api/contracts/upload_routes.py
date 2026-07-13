# -*- coding: utf-8 -*-
"""
Contract Upload Routes

Performance: Uses streaming upload (shutil.copyfileobj) to avoid loading
entire file into memory. Validates extension/magic bytes after streaming to disk.
"""
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract, ContractParty, ContractRelation, Counterparty
from src.models.auth_models import User
from src.models.contract_relations_models import RELATION_TYPES
from src.services.quota_service import contract_limit_message, get_contract_quota
from src.services.legal_consent import user_has_legal_consent
from src.utils.file_validator import (
    FileValidationError,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
    MAX_FILE_SIZE,
)
from src.api.dependencies import get_current_user
from src.api.v2.dependencies import OrganizationContext, get_org_context

from .schemas import ContractUploadResponse


router = APIRouter()

UPLOAD_DIR = "data/contracts"


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    document_type: str = Form("contract"),
    counterparty_id: Optional[str] = Form(None),
    parent_contract_id: Optional[str] = Form(None),
    relation_type: Optional[str] = Form(None),
    custom_label: Optional[str] = Form(None),
    custom_prompt: Optional[str] = Form(None),
    auto_find_parent: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Upload a contract file for analysis

    **Supported formats:** DOCX, PDF, XML, TXT
    **Max size:** 50 MB

    **document_type:** 'contract' | 'derivative' | 'disagreement' | 'tracked_changes'
    **counterparty_id:** опционально, привязать контрагента к договору (роль='counterparty')
    **parent_contract_id + relation_type:** для производных документов сразу создаст связь
    **auto_find_parent:** если document_type='derivative' и parent_contract_id не задан —
    после загрузки попытаемся найти кандидатов на основной договор по реквизитам

    **Performance:** Streams file to disk in 64KB chunks instead of loading entirely into memory.

    **Returns:** Contract ID, статус, привязки и (опционально) parent_candidates.
    """
    VALID_DOCUMENT_TYPES = {"contract", "derivative", "disagreement", "tracked_changes"}
    if not user_has_legal_consent(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Примите пользовательское соглашение и политику конфиденциальности перед загрузкой документа",
        )
    if document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Allowed: {', '.join(sorted(VALID_DOCUMENT_TYPES))}"
        )

    # Проверки до сохранения файла: связи и реквизиты
    if parent_contract_id and not relation_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="При указании parent_contract_id требуется relation_type",
        )
    if relation_type and relation_type not in RELATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый relation_type. Разрешены: {', '.join(RELATION_TYPES)}",
        )
    if relation_type == "custom" and not (
        (custom_label and custom_label.strip())
        or (custom_prompt and custom_prompt.strip())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для custom-связи укажите custom_label и/или custom_prompt",
        )

    tmp_path: Optional[str] = None
    final_path: Optional[str] = None
    upload_committed = False
    try:
        # Reset daily LLM/legacy counters if needed. Free contract uploads are limited monthly.
        current_user.reset_daily_limits()
        db.commit()

        # Check usage limits
        contract_quota = get_contract_quota(db, current_user)
        if contract_quota["used"] >= contract_quota["limit"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=contract_limit_message(contract_quota["limit"], contract_quota["period"])
            )

        # Validate optional DB links before writing the final file or creating a contract.
        # This prevents orphaned files/contracts when a selected counterparty or parent
        # contract is invalid or belongs to another organization.
        selected_counterparty: Optional[Counterparty] = None
        if counterparty_id:
            selected_counterparty = (
                db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
            )
            if not selected_counterparty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Контрагент {counterparty_id} не найден",
                )
            if (
                ctx
                and selected_counterparty.organization_id
                and selected_counterparty.organization_id != ctx.org.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Контрагент принадлежит другой организации",
                )

        selected_parent: Optional[Contract] = None
        if parent_contract_id:
            selected_parent = (
                db.query(Contract).filter(Contract.id == parent_contract_id).first()
            )
            if not selected_parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Основной договор {parent_contract_id} не найден",
                )
            if (
                selected_parent.assigned_to != current_user.id
                and current_user.role != "admin"
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет доступа к основному договору",
                )
            if (
                ctx
                and selected_parent.organization_id
                and selected_parent.organization_id != ctx.org.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Основной договор принадлежит другой организации",
                )

        # Validate filename and extension before streaming
        try:
            safe_filename = sanitize_filename(file.filename)
            ext = validate_file_extension(safe_filename)
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {e}"
            )

        # Stream file to a temporary file (64KB chunks — avoids memory spike)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=ext)
        try:
            file_size = 0
            magic_bytes = b""
            with os.fdopen(fd, "wb") as tmp_file:
                while True:
                    chunk = await file.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            f"File too large (>{MAX_FILE_SIZE // (1024*1024)} MB)"
                        )
                    if len(magic_bytes) < 100:
                        magic_bytes += chunk
                        magic_bytes = magic_bytes[:100]
                    tmp_file.write(chunk)
        except FileValidationError:
            # Clean up temp file on validation failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Validate size and magic bytes after streaming
        try:
            validate_file_size(file_size)
            if len(magic_bytes) >= 10:
                validate_mime_type(magic_bytes, ext)
        except FileValidationError as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {e}"
            )

        # Rename temp file to final safe name
        # Add collision-safe suffix if needed
        final_path = os.path.join(UPLOAD_DIR, safe_filename)
        if not os.path.abspath(final_path).startswith(os.path.abspath(UPLOAD_DIR)):
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail="Path traversal detected")

        if os.path.exists(final_path):
            name, fext = os.path.splitext(safe_filename)
            safe_filename = f"{name}_{os.urandom(8).hex()[:8]}{fext}"
            final_path = os.path.join(UPLOAD_DIR, safe_filename)

        os.rename(tmp_path, final_path)
        tmp_path = None  # Prevent cleanup in finally

        # Create contract record in database
        contract = Contract(
            file_name=safe_filename,
            file_path=final_path,
            document_type=document_type,
            contract_type='unknown',  # Will be determined during analysis
            status='uploaded',
            assigned_to=current_user.id,
            organization_id=ctx.org.id if ctx else None,
            meta_info={}
        )
        db.add(contract)
        db.flush()

        logger.info(f"Contract uploaded: {contract.id} by user {current_user.id} ({file_size} bytes, streamed)")

        # ── Привязка контрагента (если задан) ────────────────────────────────
        counterparty_party_id: Optional[str] = None
        if selected_counterparty:
            party = ContractParty(
                contract_id=contract.id,
                counterparty_id=selected_counterparty.id,
                role="counterparty",
            )
            db.add(party)
            db.flush()
            counterparty_party_id = party.id
            contract.parties_summary = [
                {
                    "counterparty_id": selected_counterparty.id,
                    "name": selected_counterparty.name,
                    "inn": selected_counterparty.inn,
                    "role": "counterparty",
                }
            ]

        # ── Привязка к основному договору (если задан явно) ──────────────────
        parent_relation_id: Optional[str] = None
        if selected_parent:
            relation = ContractRelation(
                parent_contract_id=selected_parent.id,
                child_contract_id=contract.id,
                relation_type=relation_type,
                custom_label=custom_label,
                custom_prompt=custom_prompt,
                created_by=current_user.id,
            )
            db.add(relation)
            db.flush()
            parent_relation_id = relation.id
            contract.document_type = "derivative"
            contract.primary_relation_type = relation_type

        if contract_quota["period"] == "day":
            # Atomic increment with limit re-check (prevents race condition).
            limit_value = contract_quota["limit"]
            result = db.execute(
                sql_update(User)
                .where(User.id == current_user.id)
                .where(User.contracts_today < limit_value)
                .values(contracts_today=User.contracts_today + 1)
            )
            if result.rowcount == 0:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=contract_limit_message(limit_value, "day")
                )
        else:
            db.execute(
                sql_update(User)
                .where(User.id == current_user.id)
                .values(contracts_today=User.contracts_today + 1)
            )

        db.commit()
        upload_committed = True
        db.refresh(contract)

        # ── Opportunistic parse + auto-find родителя ─────────────────────────
        parent_candidates: list = []
        if document_type == "derivative" and parent_contract_id is None and auto_find_parent:
            try:
                parsed_text = _opportunistic_parse(final_path)
                if parsed_text:
                    contract.parsed_text = parsed_text
                    db.commit()
                    from src.services.main_contract_finder import (
                        MainContractFinderService,
                    )

                    finder = MainContractFinderService()
                    candidates = finder.find_candidates(
                        db=db,
                        text=parsed_text,
                        current_user=current_user,
                        organization_id=ctx.org.id if ctx else None,
                        exclude_contract_id=contract.id,
                        limit=5,
                    )
                    parent_candidates = [
                        {
                            "contract_id": c.contract_id,
                            "file_name": c.file_name,
                            "contract_number": c.contract_number,
                            "contract_date": c.contract_date,
                            "counterparties": c.counterparties,
                            "confidence": c.confidence,
                            "matched_fields": c.matched_fields,
                        }
                        for c in candidates
                    ]
            except Exception as parse_err:  # noqa: BLE001
                # Auto-find — best effort. Парсинг файла не должен ломать загрузку.
                logger.warning(
                    f"auto_find_parent: parse/find failed for {contract.id}: {parse_err}"
                )

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='uploaded',
            message='Contract uploaded successfully',
            document_type=contract.document_type,
            primary_relation_type=contract.primary_relation_type,
            parent_relation_id=parent_relation_id,
            counterparty_party_id=counterparty_party_id,
            parent_candidates=parent_candidates,
        )

    except HTTPException:
        db.rollback()
        if final_path and not upload_committed and os.path.exists(final_path):
            os.unlink(final_path)
        raise
    except FileValidationError as e:
        db.rollback()
        if final_path and not upload_committed and os.path.exists(final_path):
            os.unlink(final_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {e}",
        )
    except Exception as e:
        db.rollback()
        if final_path and not upload_committed and os.path.exists(final_path):
            os.unlink(final_path)
        logger.error(f"Error uploading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading contract"
        )
    finally:
        # Clean up temp file if still exists (error path)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _opportunistic_parse(file_path: str) -> Optional[str]:
    """Best-effort извлечение текста из файла при загрузке.

    Используется только для auto_find_parent. Если что-то идёт не так —
    возвращает None и не ломает загрузку.
    """
    try:
        from src.services.document_parser import DocumentParser

        parser = DocumentParser()
        text = parser.parse(file_path)
        if not text:
            return None
        # Усечём для autofind: достаточно preamble + первой страницы
        return text[:10_000]
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"_opportunistic_parse failed: {exc}")
        return None
