# -*- coding: utf-8 -*-
"""
Contract Generation Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User
from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
from src.services.llm_gateway import LLMGateway
from config.settings import settings
from src.api.dependencies import get_current_user

from .schemas import (
    ContractGenerateRequest,
    ContractGenerateResponse,
    DisagreementGenerateRequest,
)


router = APIRouter()


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
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractGeneratorAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'template_id': request_data.template_id or f"tpl_{request_data.contract_type}_001",
            'contract_type': request_data.contract_type,
            'params': request_data.params,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Contract generated: {result.data.get('contract_id')} by user {current_user.id}")
            return ContractGenerateResponse(
                contract_id=result.data.get('contract_id'),
                file_path=result.data.get('file_path'),
                status='generated',
                message='Contract generated successfully'
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Contract generation failed: {result.error}"
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
