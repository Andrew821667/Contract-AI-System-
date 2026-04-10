# -*- coding: utf-8 -*-
"""
Template Routes — создание шаблонов генерации из проанализированных договоров
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger

from src.models.database import get_db, Contract, Template, AnalysisResult
from src.models.auth_models import User
from src.api.dependencies import get_current_user


router = APIRouter()


class SaveAsTemplateRequest(BaseModel):
    name: str = Field(..., description="Название шаблона")
    contract_type: str = Field(..., description="Тип договора (supply, service, lease, etc.)")


class SaveAsTemplateResponse(BaseModel):
    template_id: str
    name: str
    contract_type: str
    message: str


class TemplateListItem(BaseModel):
    id: str
    name: str
    contract_type: str
    version: Optional[str] = None
    source_file_name: Optional[str] = None


class TemplateStatusResponse(BaseModel):
    has_template: bool
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    contract_type: Optional[str] = None


@router.get("/templates", response_model=List[TemplateListItem])
async def list_templates(
    contract_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Список всех активных шаблонов для генерации.
    Опционально фильтрация по типу договора.
    """
    query = db.query(Template).filter(Template.active == True)
    if contract_type:
        query = query.filter(Template.contract_type == contract_type)
    query = query.order_by(Template.contract_type, Template.name)
    templates = query.all()

    return [
        TemplateListItem(
            id=t.id,
            name=t.name,
            contract_type=t.contract_type,
            version=t.version,
            source_file_name=(t.meta_info or {}).get("source_file_name"),
        )
        for t in templates
    ]


@router.get("/{contract_id}/template-status", response_model=TemplateStatusResponse)
async def get_template_status(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Проверить, сохранён ли этот договор как шаблон для генерации.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Договор не найден")

    # Проверяем, есть ли шаблон, созданный из этого договора
    template = (
        db.query(Template)
        .filter(
            Template.meta_info["source_contract_id"].as_string() == contract_id,
            Template.active == True,
        )
        .first()
    )

    if template:
        return TemplateStatusResponse(
            has_template=True,
            template_id=template.id,
            template_name=template.name,
            contract_type=template.contract_type,
        )

    return TemplateStatusResponse(has_template=False)


@router.post("/{contract_id}/save-as-template", response_model=SaveAsTemplateResponse)
async def save_contract_as_template(
    contract_id: str,
    request_data: SaveAsTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Сохранить проанализированный договор как шаблон для генерации.

    Доступно только для завершённых анализов (status=completed).
    Пользователь сам решает, добавлять ли договор как образец.
    """
    # Получаем договор
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Договор не найден")

    if contract.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Договор должен быть проанализирован перед сохранением как шаблон",
        )

    # Проверяем, что анализ есть
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.contract_id == contract_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=400, detail="Результаты анализа не найдены")

    # Проверяем, что шаблон из этого договора ещё не создан
    existing = (
        db.query(Template)
        .filter(
            Template.meta_info["source_contract_id"].as_string() == contract_id,
            Template.active == True,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Шаблон из этого договора уже существует: {existing.name}",
        )

    # Читаем XML-содержимое договора
    xml_content = ""
    try:
        import os
        file_path = contract.file_path
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                xml_content = f.read()
        else:
            # Попробуем в контейнере
            container_path = f"/app/uploads/{os.path.basename(file_path)}"
            if os.path.exists(container_path):
                with open(container_path, "r", encoding="utf-8") as f:
                    xml_content = f.read()
    except Exception as e:
        logger.warning(f"Не удалось прочитать файл договора: {e}")

    if not xml_content:
        # Если файл не читается, используем данные из анализа
        xml_content = f"<!-- Шаблон создан из договора {contract.file_name} -->"

    # Определяем версию — ищем существующие шаблоны этого типа
    existing_versions = (
        db.query(Template)
        .filter(Template.contract_type == request_data.contract_type)
        .count()
    )
    version = f"{existing_versions + 1}.0"

    # Создаём шаблон
    from src.models.database import generate_uuid
    template = Template(
        id=generate_uuid(),
        name=request_data.name,
        contract_type=request_data.contract_type,
        xml_content=xml_content,
        structure=None,
        meta_info={
            "source_contract_id": contract_id,
            "source_file_name": contract.file_name,
            "created_from_analysis": True,
            "analysis_id": analysis.id,
            "risk_level": contract.risk_level,
        },
        version=version,
        active=True,
        created_by=current_user.id,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info(
        f"Шаблон создан из договора: template_id={template.id}, "
        f"contract_id={contract_id}, type={request_data.contract_type}, "
        f"user={current_user.id}"
    )

    return SaveAsTemplateResponse(
        template_id=template.id,
        name=template.name,
        contract_type=template.contract_type,
        message=f"Шаблон «{template.name}» успешно создан",
    )
