# -*- coding: utf-8 -*-
"""
Bridge API — эндпоинты для интеграции с Legal AI Platform.

Позволяет внешней платформе:
- Проверять статус Contract-AI-System
- Отправлять файлы на анализ
- Отслеживать прогресс анализа
- Получать результаты в разных форматах (JSON, summary, PDF)

Аутентификация: shared secret через заголовок X-Bridge-Secret.
"""
import os
import shutil
import tempfile
import json
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db, Contract, AnalysisResult
from src.models.auth_models import User
from src.utils.file_validator import (
    sanitize_filename,
    validate_file_extension,
    validate_mime_type,
    MAX_FILE_SIZE,
)

router = APIRouter()

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")
UPLOAD_DIR = "data/contracts"


# ─── Auth ────────────────────────────────────────────────────

def verify_bridge_secret(x_bridge_secret: str = Header(..., alias="X-Bridge-Secret")):
    """Проверка shared secret для bridge-запросов."""
    if not BRIDGE_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bridge not configured (BRIDGE_SECRET not set)"
        )
    import hmac
    if not hmac.compare_digest(x_bridge_secret, BRIDGE_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bridge secret"
        )
    return True


# ─── Schemas ─────────────────────────────────────────────────

class BridgeStatusResponse(BaseModel):
    mode: str = Field(description="online | busy | offline")
    version: str = "3.0"
    capabilities: list = Field(default_factory=list)
    active_analyses: int = 0
    max_concurrent: int = 10

class BridgeAnalyzeResponse(BaseModel):
    job_id: str = Field(description="Contract ID for tracking")
    status: str = "queued"
    message: str = ""

class BridgeProgressResponse(BaseModel):
    job_id: str
    status: str
    percent: int = 0
    message: str = ""

class BridgeResultResponse(BaseModel):
    job_id: str
    status: str
    risks: list = Field(default_factory=list)
    recommendations: list = Field(default_factory=list)
    suggested_changes: list = Field(default_factory=list)
    full_text_analysis: Optional[Dict[str, Any]] = None
    summary: str = ""
    risk_score: float = 0.0


# ─── GET /status ─────────────────────────────────────────────

@router.get("/status", response_model=BridgeStatusResponse)
async def bridge_status(
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    Проверка статуса Contract-AI-System.
    Возвращает текущий режим работы и возможности.
    """
    try:
        # Подсчёт активных анализов
        active = db.query(Contract).filter(Contract.status == 'analyzing').count()

        mode = "online"
        if active >= 10:
            mode = "busy"

        return BridgeStatusResponse(
            mode=mode,
            version="3.0",
            capabilities=[
                "contract_analysis",
                "risk_identification",
                "recommendations",
                "full_text_analysis",
                "company_conditions",
                "rag_context",
                "pdf_report",
            ],
            active_analyses=active,
            max_concurrent=10,
        )
    except Exception as e:
        logger.error(f"Bridge status check failed: {e}")
        return BridgeStatusResponse(mode="offline", version="3.0")


# ─── POST /analyze ───────────────────────────────────────────

@router.post("/analyze", response_model=BridgeAnalyzeResponse)
async def bridge_analyze(
    file: UploadFile = File(...),
    document_type: str = Form("contract"),
    user_email: str = Form(...),
    user_name: str = Form(""),
    org_id: str = Form(""),
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    Принять файл на анализ от Legal AI Platform.

    1. Находит/создаёт пользователя по email
    2. Сохраняет файл
    3. Запускает анализ в фоне
    4. Возвращает job_id для отслеживания
    """
    from src.services.auth_service import AuthService

    # Валидация файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    safe_name = sanitize_filename(file.filename)
    ext = os.path.splitext(safe_name)[1].lower()

    try:
        validate_file_extension(safe_name)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Найти или создать пользователя
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        # Создаём bridge-пользователя с ролью demo
        import uuid
        import secrets
        user = User(
            id=str(uuid.uuid4()),
            email=user_email,
            name=user_name or user_email.split("@")[0],
            role="demo",
            password_hash=f"!bridge_sso_{secrets.token_hex(16)}",  # Non-loginable marker
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Bridge: created user {user_email} (id={user.id})")

    # Сохранить файл
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    import uuid
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        # Проверка размера
        file_size = os.path.getsize(tmp_path)
        if file_size > MAX_FILE_SIZE:
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail=f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})")

        # Перемещаем в upload dir
        shutil.move(tmp_path, file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    # Создаём запись договора
    contract = Contract(
        id=file_id,
        filename=safe_name,
        file_path=file_path,
        file_type=ext.lstrip('.'),
        file_size=file_size,
        document_type=document_type,
        status='uploaded',
        assigned_to=user.id,
        meta_info=json.dumps({
            "source": "bridge",
            "org_id": org_id,
            "platform": "legal-ai-platform",
        }),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    # Запуск анализа в фоне
    try:
        from src.api.contracts.analysis_routes import analyze_contract_background
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(analyze_contract_background(
            contract_id=contract.id,
            user_id=user.id,
            check_counterparty=False,
            counterparty_tin=None,
        ))
        logger.info(f"Bridge: analysis started for contract {contract.id}")
    except Exception as e:
        logger.error(f"Bridge: failed to start analysis: {e}")
        # Не блокируем — пользователь может запустить анализ вручную

    return BridgeAnalyzeResponse(
        job_id=contract.id,
        status="analyzing",
        message=f"Файл {safe_name} принят на анализ",
    )


# ─── GET /progress/{job_id} ─────────────────────────────────

@router.get("/progress/{job_id}", response_model=BridgeProgressResponse)
async def bridge_progress(
    job_id: str,
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    Прогресс анализа. Для polling из Telegram-бота и фронтенда.
    """
    contract = db.query(Contract).filter(Contract.id == job_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Job not found")

    # Прогресс хранится в meta_info._progress
    meta = {}
    if contract.meta_info:
        try:
            meta = json.loads(contract.meta_info) if isinstance(contract.meta_info, str) else contract.meta_info
        except (json.JSONDecodeError, TypeError):
            pass

    percent = meta.get("_progress", 0)
    message = meta.get("_progress_msg", "")

    if contract.status == 'analyzed':
        percent = 100
        message = "Анализ завершён"
    elif contract.status == 'error':
        message = "Ошибка анализа"
    elif contract.status == 'uploaded':
        percent = 0
        message = "Ожидает анализа"

    return BridgeProgressResponse(
        job_id=job_id,
        status=contract.status,
        percent=percent,
        message=message,
    )


# ─── GET /result/{job_id} ───────────────────────────────────

@router.get("/result/{job_id}", response_model=BridgeResultResponse)
async def bridge_result(
    job_id: str,
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    Полные результаты анализа в JSON.
    """
    contract = db.query(Contract).filter(Contract.id == job_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Job not found")

    if contract.status not in ('analyzed', 'completed'):
        return BridgeResultResponse(
            job_id=job_id,
            status=contract.status,
            summary="Анализ ещё не завершён" if contract.status == 'analyzing' else "Анализ не выполнен",
        )

    # Загружаем результаты из нормализованных таблиц
    from src.models.analyzer_models import ContractRisk, ContractRecommendation, ContractSuggestedChange

    analysis = db.query(AnalysisResult).filter(
        AnalysisResult.contract_id == job_id
    ).order_by(AnalysisResult.created_at.desc()).first()

    risks = []
    recommendations = []
    suggested_changes = []
    full_text_data = None

    if analysis:
        # Риски
        risk_rows = db.query(ContractRisk).filter(
            ContractRisk.analysis_id == analysis.id
        ).all()
        risks = [
            {
                "type": r.risk_type,
                "severity": r.severity,
                "probability": r.probability,
                "title": r.title,
                "description": r.description,
                "consequences": r.consequences or "",
                "section": r.section_name or "",
            }
            for r in risk_rows
        ]

        # Рекомендации
        rec_rows = db.query(ContractRecommendation).filter(
            ContractRecommendation.analysis_id == analysis.id
        ).all()
        recommendations = [
            {
                "category": r.category,
                "priority": r.priority,
                "title": r.title,
                "description": r.description,
                "reasoning": r.reasoning or "",
            }
            for r in rec_rows
        ]

        # Предлагаемые изменения
        change_rows = db.query(ContractSuggestedChange).filter(
            ContractSuggestedChange.analysis_id == analysis.id
        ).all()
        suggested_changes = [
            {
                "section": c.section_name or "",
                "original_text": c.original_text,
                "suggested_text": c.suggested_text,
                "issue": c.issue,
                "reasoning": c.reasoning or "",
            }
            for c in change_rows
        ]

        # Full-text analysis из meta
        try:
            meta = json.loads(analysis.risks_by_category) if analysis.risks_by_category else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}

    # Risk score: доля critical+high рисков
    total_risks = len(risks)
    critical_high = sum(1 for r in risks if r['severity'] in ('critical', 'high'))
    risk_score = critical_high / max(total_risks, 1)

    # Summary
    summary = _build_summary(contract, risks, recommendations)

    return BridgeResultResponse(
        job_id=job_id,
        status=contract.status,
        risks=risks,
        recommendations=recommendations,
        suggested_changes=suggested_changes,
        full_text_analysis=full_text_data,
        summary=summary,
        risk_score=round(risk_score, 2),
    )


# ─── GET /result/{job_id}/summary ───────────────────────────

@router.get("/result/{job_id}/summary")
async def bridge_result_summary(
    job_id: str,
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    Краткий текстовый отчёт для Telegram (markdown, до 4096 символов).
    """
    contract = db.query(Contract).filter(Contract.id == job_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Job not found")

    if contract.status not in ('analyzed', 'completed'):
        return {"summary": "Анализ ещё не завершён.", "status": contract.status}

    # Загружаем данные
    from src.models.analyzer_models import ContractRisk, ContractRecommendation

    analysis = db.query(AnalysisResult).filter(
        AnalysisResult.contract_id == job_id
    ).order_by(AnalysisResult.created_at.desc()).first()

    if not analysis:
        return {"summary": "Результаты анализа не найдены.", "status": contract.status}

    risks = db.query(ContractRisk).filter(
        ContractRisk.analysis_id == analysis.id
    ).order_by(
        ContractRisk.severity.desc()
    ).all()

    recs = db.query(ContractRecommendation).filter(
        ContractRecommendation.analysis_id == analysis.id
    ).order_by(
        ContractRecommendation.priority.desc()
    ).limit(5).all()

    # Формируем markdown-отчёт
    lines = []
    lines.append(f"**Анализ договора: {contract.filename}**")
    lines.append("")

    # Статистика рисков
    severity_counts = {}
    for r in risks:
        severity_counts[r.severity] = severity_counts.get(r.severity, 0) + 1

    severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
    severity_labels = {'critical': 'Критических', 'high': 'Высоких', 'medium': 'Средних', 'low': 'Низких'}

    lines.append(f"**Найдено рисков: {len(risks)}**")
    for sev in ('critical', 'high', 'medium', 'low'):
        count = severity_counts.get(sev, 0)
        if count:
            lines.append(f"{severity_emoji.get(sev, '⚪')} {severity_labels.get(sev, sev)}: {count}")
    lines.append("")

    # Top-5 рисков
    top_risks = risks[:5]
    if top_risks:
        lines.append("**Ключевые риски:**")
        for i, r in enumerate(top_risks, 1):
            emoji = severity_emoji.get(r.severity, '⚪')
            lines.append(f"{i}. {emoji} **{r.title}**")
            if r.description:
                desc = r.description[:150]
                if len(r.description) > 150:
                    desc += "..."
                lines.append(f"   {desc}")
        lines.append("")

    # Top рекомендации
    if recs:
        lines.append("**Рекомендации:**")
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r.title}")
        lines.append("")

    lines.append("_Полный отчёт доступен в веб-кабинете._")

    summary = "\n".join(lines)

    # Обрезаем до лимита Telegram (4096)
    if len(summary) > 4000:
        summary = summary[:3997] + "..."

    return {"summary": summary, "status": contract.status, "risk_count": len(risks)}


# ─── GET /result/{job_id}/pdf ────────────────────────────────

@router.get("/result/{job_id}/pdf")
async def bridge_result_pdf(
    job_id: str,
    _: bool = Depends(verify_bridge_secret),
    db: Session = Depends(get_db)
):
    """
    PDF-отчёт по результатам анализа.
    """
    contract = db.query(Contract).filter(Contract.id == job_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Job not found")

    if contract.status not in ('analyzed', 'completed'):
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    # Проверяем наличие готового PDF
    pdf_path = os.path.join("data/exports", f"report_{job_id}.pdf")
    if os.path.exists(pdf_path):
        return StreamingResponse(
            open(pdf_path, "rb"),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{contract.filename}.pdf"}
        )

    # Генерируем PDF на лету
    try:
        pdf_bytes = _generate_pdf_report(contract, db)
        if pdf_bytes:
            import io
            os.makedirs("data/exports", exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=report_{contract.filename}.pdf"}
            )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")

    raise HTTPException(status_code=501, detail="PDF generation not available")


# ─── Helpers ─────────────────────────────────────────────────

def _build_summary(contract: Contract, risks: list, recommendations: list) -> str:
    """Краткое текстовое резюме для JSON-ответа."""
    total = len(risks)
    critical = sum(1 for r in risks if r['severity'] == 'critical')
    high = sum(1 for r in risks if r['severity'] == 'high')

    parts = [f"Договор '{contract.filename}': найдено {total} рисков"]
    if critical:
        parts.append(f"{critical} критических")
    if high:
        parts.append(f"{high} высоких")
    parts.append(f"{len(recommendations)} рекомендаций")
    return ", ".join(parts) + "."


def _generate_pdf_report(contract: Contract, db: Session) -> Optional[bytes]:
    """
    Генерация PDF-отчёта. Использует reportlab если доступен.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        # Пытаемся зарегистрировать кириллический шрифт
        try:
            pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            base_font = 'DejaVu'
        except Exception:
            base_font = 'Helvetica'

        title_style = ParagraphStyle('Title_RU', parent=styles['Title'], fontName=base_font, fontSize=16)
        heading_style = ParagraphStyle('Heading_RU', parent=styles['Heading2'], fontName=base_font, fontSize=13)
        body_style = ParagraphStyle('Body_RU', parent=styles['Normal'], fontName=base_font, fontSize=10)

        story = []

        # Заголовок
        story.append(Paragraph(f"Otchet po analizu dogovora", title_style))
        story.append(Paragraph(f"Fayl: {contract.filename}", body_style))
        story.append(Paragraph(f"Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}", body_style))
        story.append(Spacer(1, 20))

        # Риски
        from src.models.analyzer_models import ContractRisk, ContractRecommendation
        analysis = db.query(AnalysisResult).filter(
            AnalysisResult.contract_id == contract.id
        ).order_by(AnalysisResult.created_at.desc()).first()

        if analysis:
            risks = db.query(ContractRisk).filter(ContractRisk.analysis_id == analysis.id).all()
            story.append(Paragraph(f"Riski ({len(risks)})", heading_style))
            story.append(Spacer(1, 10))

            for r in risks:
                story.append(Paragraph(
                    f"[{r.severity}] {r.title}: {r.description or ''}",
                    body_style
                ))
                story.append(Spacer(1, 5))

            story.append(Spacer(1, 15))

            # Рекомендации
            recs = db.query(ContractRecommendation).filter(
                ContractRecommendation.analysis_id == analysis.id
            ).all()
            story.append(Paragraph(f"Rekomendacii ({len(recs)})", heading_style))
            story.append(Spacer(1, 10))

            for r in recs:
                story.append(Paragraph(f"[{r.priority}] {r.title}: {r.description or ''}", body_style))
                story.append(Spacer(1, 5))

        story.append(Spacer(1, 20))
        story.append(Paragraph(
            "Disclaimer: Rezultaty AI-analiza nosyat rekomendatelnyy kharakter.",
            body_style
        ))

        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        logger.warning("reportlab not installed, PDF generation unavailable")
        return None
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None
