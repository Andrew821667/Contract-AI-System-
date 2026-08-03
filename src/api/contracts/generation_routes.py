# -*- coding: utf-8 -*-
"""
Contract Generation Routes
"""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User
from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
from src.services.llm_gateway import LLMGateway
from src.utils.contract_types import get_generation_contract_types as get_generation_contract_type_catalog
from config.settings import settings
from src.api.dependencies import get_current_user

from .schemas import (
    ContractGenerateRequest,
    ContractGenerateResponse,
    ContractTypeOption,
    DisagreementGenerateRequest,
)


router = APIRouter()


@router.get("/generate/types", response_model=list[ContractTypeOption])
async def list_generation_contract_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return contract types available for generation: built-in + analyzed custom types."""
    include_all = current_user.role == "admin"
    items = get_generation_contract_type_catalog(
        db,
        user_id=current_user.id,
        include_all=include_all,
    )
    return [ContractTypeOption(**item) for item in items]


@router.post("/generate", response_model=ContractGenerateResponse)
async def generate_contract(
    request_data: ContractGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a new contract from template

    **Contract types:**
    - supply: Договор поставки
    - service: Договор услуг
    - lease: Договор аренды
    - purchase: Договор купли-продажи
    - confidentiality: Соглашение о конфиденциальности

    **Returns:** Generated contract ID and file path
    """
    try:
        # Раньше здесь звался ContractGeneratorAgent, но он спроектирован под
        # генерацию ИЗ уже загруженного договора и требует в состоянии
        # contract_id + parsed_xml. Эндпоинт передавал тип и параметры формы,
        # проверка состояния падала, и генерация из интерфейса отдавала 500 —
        # по любому типу, при любых данных. ContractGenerationService делает
        # ровно то, что нужно этому эндпоинту: параметры → текст → DOCX.
        from src.services.contract_generation_service import (
            ContractGenerationService,
            ContractParams,
            ContractParty,
        )
        from src.models.database import Contract, Template, generate_uuid

        p = request_data.params or {}

        # Типовой шаблон организации для этого типа, если заведён.
        template_text = ""
        tpl = (
            db.query(Template)
            .filter(Template.contract_type == request_data.contract_type, Template.active == True)  # noqa: E712
            .order_by(Template.created_at.desc())
            .first()
        )
        if tpl and tpl.xml_content:
            template_text = tpl.xml_content

        gen_params = ContractParams(
            contract_type=request_data.contract_type,
            party_a=ContractParty(name=str(p.get("party_a") or "")),
            party_b=ContractParty(name=str(p.get("party_b") or "")),
            subject=str(p.get("subject") or ""),
            amount=str(p.get("amount") or ""),
            start_date=str(p.get("start_date") or ""),
            duration=str(p.get("end_date") or ""),
            payment_terms=str(p.get("payment_terms") or ""),
            additional_conditions=str(p.get("additional_terms") or ""),
        )

        result = ContractGenerationService().generate(gen_params, template_text=template_text)

        if not result.success:
            # Текст ошибки провайдера пишем в лог, наружу не отдаём: он содержит
            # диагностику вызова вплоть до хвоста API-ключа.
            logger.error(
                f"Генерация не удалась (тип={request_data.contract_type}, "
                f"пользователь={current_user.id}): {result.error}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось сгенерировать договор: сервис генерации недоступен. Попробуйте позже.",
            )

        # Сохраняем результат как договор — иначе интерфейсу некуда переходить
        # после генерации (он открывает /contracts/{id}).
        contract = Contract(
            id=generate_uuid(),
            file_name=os.path.basename(result.docx_path),
            file_path=result.docx_path,
            document_type="generated",
            contract_type=request_data.contract_type,
            status="completed",
            assigned_to=current_user.id,
            meta_info={
                "origin": "generated",
                "template_id": tpl.id if tpl else None,
                "generated_from_params": p,
            },
        )
        db.add(contract)
        db.commit()

        logger.info(
            f"Договор сгенерирован: {contract.id} тип={request_data.contract_type} "
            f"шаблон={'да' if tpl else 'нет'} пользователь={current_user.id}"
        )
        return ContractGenerateResponse(
            contract_id=contract.id,
            file_path=result.docx_path,
            status="generated",
            message="Contract generated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating contract"
        )


@router.post("/disagreements")
async def generate_disagreements(
    request_data: DisagreementGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate disagreement document with legal justifications

    **Process:**
    1. Retrieve contract analysis results
    2. Prioritize risks by severity
    3. Generate legal objections for each risk
    4. Format for ЭДО (electronic document management)

    **Returns:** Disagreement document ID and objections list
    """
    try:
        # Ownership check
        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access this contract")

        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = DisagreementProcessorAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': request_data.contract_id,
            'analysis_id': request_data.analysis_id,
            'auto_prioritize': request_data.auto_prioritize,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Disagreements generated for contract {request_data.contract_id}")
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Disagreement generation failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating disagreements: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
