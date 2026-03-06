# -*- coding: utf-8 -*-
"""
Contract Operations API Routes
Upload, analyze, generate, and export contracts
"""
import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field

from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.models.changes_models import ContractVersion, ContractChange, ChangeAnalysisResult
from src.services.auth_service import AuthService
from src.services.document_parser import DocumentParser
from src.services.document_diff_service import DocumentDiffService
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
from src.agents.changes_analyzer_agent import ChangesAnalyzerAgent
from src.agents.quick_export_agent import QuickExportAgent
from src.services.llm_gateway import LLMGateway
from src.utils.file_validator import save_uploaded_file_securely, FileValidationError
from config.settings import settings
from src.services.digital_service import DigitalContractService
from src.services.clause_library_service import ClauseLibraryService
from src.services.clause_extractor import ClauseExtractor


router = APIRouter()


# Dependency: Get current user from token
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)
    
    # Verify token
    payload = auth_service.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
        
    if not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    return user


# Pydantic schemas
class ContractUploadResponse(BaseModel):
    contract_id: str
    file_name: str
    file_size: int
    status: str
    message: str


class AnalysisResultRequest(BaseModel):
    contract_id: str
    check_counterparty: bool = True
    counterparty_tin: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    analysis_id: str
    contract_id: str
    status: str
    risks_count: int
    recommendations_count: int
    message: str


class ContractGenerateRequest(BaseModel):
    contract_type: str = Field(..., description="Type of contract (supply, service, lease, etc.)")
    template_id: Optional[str] = None
    params: Dict[str, Any] = Field(..., description="Contract parameters")


class ContractGenerateResponse(BaseModel):
    contract_id: str
    file_path: str
    status: str
    message: str


class DisagreementGenerateRequest(BaseModel):
    contract_id: str
    analysis_id: str
    auto_prioritize: bool = True


class ExportRequest(BaseModel):
    contract_id: str
    export_format: str = Field(..., description="Format: docx, pdf, txt, json, xml, all")
    include_analysis: bool = False


class ContractListResponse(BaseModel):
    contracts: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class ContractVersionResponse(BaseModel):
    id: int
    contract_id: str
    version_number: int
    file_hash: Optional[str] = None
    source: str
    description: Optional[str] = None
    is_current: bool
    uploaded_at: Optional[str] = None


class CompareRequest(BaseModel):
    from_version_id: int
    to_version_id: int


class CompareChangeItem(BaseModel):
    change_type: str
    change_category: str
    section_name: Optional[str] = None
    clause_number: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    xpath_location: Optional[str] = None


class CompareResultResponse(BaseModel):
    total_changes: int
    by_type: Dict[str, int]
    by_category: Dict[str, int]
    overall_assessment: Optional[str] = None
    changes: List[CompareChangeItem]
    executive_summary: Optional[str] = None


# ==================== CONTRACT UPLOAD ====================

@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    document_type: str = Form("contract"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a contract file for analysis

    **Supported formats:** DOCX, PDF, XML, TXT
    **Max size:** 10 MB

    **Returns:** Contract ID and status
    """
    try:
        # Read file data
        file_data = await file.read()

        # Validate and save file securely
        try:
            file_path, safe_filename, file_size = save_uploaded_file_securely(
                file_data=file_data,
                filename=file.filename,
                upload_dir="data/contracts"
            )
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {str(e)}"
            )

        # Create contract record in database
        contract = Contract(
            file_name=safe_filename,
            file_path=file_path,
            document_type=document_type,
            contract_type='unknown',  # Will be determined during analysis
            status='uploaded',
            assigned_to=current_user.id,
            meta_info={}
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        logger.info(f"Contract uploaded: {contract.id} by user {current_user.id}")

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='uploaded',
            message='Contract uploaded successfully'
        )

    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading contract: {str(e)}"
        )


# ==================== CONTRACT ANALYSIS ====================

async def analyze_contract_background(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str],
):
    """Background task for contract analysis — creates its own DB session"""
    from src.models.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"Contract {contract_id} not found for background analysis")
            return

        # Update status
        contract.status = 'analyzing'
        db.commit()

        # Parse document
        parser = DocumentParser()
        parsed_xml = parser.parse(contract.file_path)

        if not parsed_xml:
            contract.status = 'error'
            db.commit()
            logger.error(f"Failed to parse contract {contract_id}")
            return

        # Store XML in contract
        contract.meta_info = {'xml': parsed_xml}
        db.commit()

        # Analyze with agent
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': contract_id,
            'parsed_xml': parsed_xml,
            'check_counterparty': check_counterparty,
            'metadata': {
                'counterparty_tin': counterparty_tin,
                'uploaded_by': user_id
            }
        })

        if result.success:
            contract.status = 'completed'
            logger.info(f"Contract {contract_id} analyzed successfully")

            # Auto-save extracted clauses to library
            try:
                xml_content = parsed_xml if isinstance(parsed_xml, str) else str(parsed_xml)
                extractor = ClauseExtractor()
                clauses = extractor.extract_clauses(xml_content)

                # Get analysis data from the result if available
                analyses = []
                if result.data and isinstance(result.data, dict):
                    analyses = result.data.get('clause_analyses', [])

                if clauses:
                    clause_service = ClauseLibraryService(db)
                    clause_service.save_clauses(contract_id, clauses, analyses)
                    logger.info(f"Contract {contract_id}: {len(clauses)} clauses saved to library")
            except Exception as clause_err:
                logger.warning(f"Auto clause extraction failed for {contract_id}: {clause_err}")

            # Auto-digitalize after successful analysis
            try:
                if contract.file_path and os.path.exists(contract.file_path):
                    with open(contract.file_path, "rb") as f:
                        file_content = f.read()
                    digital_service = DigitalContractService(db)
                    digital_service.digitalize(contract_id, file_content, user_id)
                    logger.info(f"Contract {contract_id} auto-digitalized")
            except Exception as dig_err:
                logger.warning(f"Auto-digitalization failed for {contract_id}: {dig_err}")
        else:
            contract.status = 'error'
            logger.error(f"Contract {contract_id} analysis failed: {result.error}")

        db.commit()

    except Exception as e:
        logger.error(f"Background analysis error for contract {contract_id}: {e}", exc_info=True)
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                contract.status = 'error'
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_contract(
    request_data: AnalysisResultRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an uploaded contract

    **Process:**
    1. Parse document to XML
    2. Extract contract structure
    3. Analyze each clause for risks
    4. Check legal compliance
    5. Generate recommendations
    6. (Optional) Check counterparty via ФНС API

    **Returns:** Analysis ID and initial status
    **Note:** Analysis runs in background. Use WebSocket or polling to get results.
    """
    try:
        # Get contract
        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to analyze this contract"
            )

        # Create analysis record
        analysis_id = str(uuid.uuid4())

        # Start background task
        background_tasks.add_task(
            analyze_contract_background,
            contract_id=request_data.contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            counterparty_tin=request_data.counterparty_tin,
        )

        logger.info(f"Analysis started for contract {request_data.contract_id} by user {current_user.id}")

        return AnalysisResultResponse(
            analysis_id=analysis_id,
            contract_id=request_data.contract_id,
            status='analyzing',
            risks_count=0,
            recommendations_count=0,
            message='Analysis started. Use WebSocket /ws/analysis/{contract_id} to track progress.'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting analysis: {str(e)}"
        )


# ==================== CONTRACT GENERATION ====================

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
            detail=f"Error generating contract: {str(e)}"
        )


# ==================== DISAGREEMENTS ====================

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
            detail=f"Error: {str(e)}"
        )


# ==================== EXPORT ====================

@router.post("/export")
async def export_contract(
    request_data: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export contract to various formats

    **Formats:**
    - docx: Microsoft Word
    - pdf: PDF document
    - txt: Plain text
    - json: JSON data
    - xml: XML format
    - all: All formats

    **Returns:** Download links for requested formats
    """
    try:
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = QuickExportAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': request_data.contract_id,
            'export_format': request_data.export_format,
            'include_analysis': request_data.include_analysis,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Contract exported: {request_data.contract_id} to {request_data.export_format}")
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CONTRACT LISTING ====================

@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List contracts for current user

    **Filters:**
    - status: uploaded, analyzing, completed, error
    - contract_type: supply, service, lease, etc.

    **Returns:** Paginated list of contracts
    """
    try:
        # Cap page_size
        if page_size > 100:
            page_size = 100
        if page < 1:
            page = 1

        query = db.query(Contract)

        # Filter by user (non-admins can only see their own contracts)
        if current_user.role not in ['admin', 'manager']:
            query = query.filter(Contract.assigned_to == current_user.id)

        # Apply filters
        if status:
            query = query.filter(Contract.status == status)
        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)

        # Get total count
        total = query.count()

        # Paginate
        contracts = query.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # Format response
        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None
            })

        return ContractListResponse(
            contracts=contracts_data,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CONTRACT DETAILS ====================

@router.get("/{contract_id}")
async def get_contract_details(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contract details including analysis results"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this contract"
            )

        # Get analysis results if available
        analysis = db.query(AnalysisResult).filter(AnalysisResult.contract_id == contract_id).first()

        return {
            'contract': {
                'id': contract.id,
                'file_name': contract.file_name,
                'file_path': contract.file_path,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            },
            'analysis': {
                'id': analysis.id if analysis else None,
                'risks': analysis.risks_by_category if analysis else [],
                'recommendations': analysis.recommendations if analysis else [],
                'status': analysis.status if analysis else None
            } if analysis else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== DOWNLOAD ====================

@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original contract file"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to download this contract"
            )

        if not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract file not found on disk"
            )

        return FileResponse(
            path=contract.file_path,
            filename=contract.file_name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CONTRACT VERSIONS ====================

@router.post("/{contract_id}/versions", response_model=ContractVersionResponse)
async def upload_version(
    contract_id: str,
    file: UploadFile = File(...),
    source: str = Form("unknown"),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a new version of a contract file"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        # Read and save file
        file_data = await file.read()

        try:
            file_path, safe_filename, file_size = save_uploaded_file_securely(
                file_data=file_data,
                filename=file.filename,
                upload_dir="data/contracts/versions"
            )
        except FileValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File validation failed: {str(e)}")

        # Compute SHA-256 hash
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Determine next version number
        max_version = db.query(func.max(ContractVersion.version_number)).filter(
            ContractVersion.contract_id == contract_id
        ).scalar() or 0
        next_version = max_version + 1

        # Mark previous versions as not current
        db.query(ContractVersion).filter(
            ContractVersion.contract_id == contract_id,
            ContractVersion.is_current == True
        ).update({'is_current': False})

        # Create new version
        version = ContractVersion(
            contract_id=contract_id,
            version_number=next_version,
            file_path=file_path,
            file_hash=file_hash,
            uploaded_by=current_user.id,
            source=source if source in ('initial', 'counterparty_response', 'internal_revision', 'final', 'unknown') else 'unknown',
            description=description or None,
            is_current=True
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        logger.info(f"Version {next_version} uploaded for contract {contract_id}")

        return ContractVersionResponse(
            id=version.id,
            contract_id=version.contract_id,
            version_number=version.version_number,
            file_hash=version.file_hash,
            source=version.source,
            description=version.description,
            is_current=version.is_current,
            uploaded_at=version.uploaded_at.isoformat() if version.uploaded_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading version: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {str(e)}")


@router.get("/{contract_id}/versions")
async def list_versions(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all versions of a contract"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        versions = db.query(ContractVersion).filter(
            ContractVersion.contract_id == contract_id
        ).order_by(ContractVersion.version_number.desc()).all()

        versions_data = []
        for v in versions:
            versions_data.append({
                'id': v.id,
                'contract_id': v.contract_id,
                'version_number': v.version_number,
                'file_hash': v.file_hash,
                'source': v.source,
                'description': v.description,
                'is_current': v.is_current,
                'uploaded_at': v.uploaded_at.isoformat() if v.uploaded_at else None
            })

        return {
            'versions': versions_data,
            'total': len(versions_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing versions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {str(e)}")


@router.post("/{contract_id}/compare", response_model=CompareResultResponse)
async def compare_versions(
    contract_id: str,
    request_data: CompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare two versions of a contract"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        # Load both versions
        from_version = db.query(ContractVersion).filter(
            ContractVersion.id == request_data.from_version_id,
            ContractVersion.contract_id == contract_id
        ).first()
        to_version = db.query(ContractVersion).filter(
            ContractVersion.id == request_data.to_version_id,
            ContractVersion.contract_id == contract_id
        ).first()

        if not from_version or not to_version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

        # Check files exist
        if not os.path.exists(from_version.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source version file not found on disk")
        if not os.path.exists(to_version.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version file not found on disk")

        # Parse both files
        parser = DocumentParser()
        old_xml = parser.parse(from_version.file_path)
        new_xml = parser.parse(to_version.file_path)

        if not old_xml or not new_xml:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Failed to parse one or both files")

        # Run diff
        diff_service = DocumentDiffService()

        # Use text mode if XML parsing might fail (non-XML content)
        try:
            changes_raw = diff_service.compare_documents(old_xml, new_xml, mode='combined')
        except Exception:
            changes_raw = diff_service.compare_documents(old_xml, new_xml, mode='text')

        # Build statistics
        by_type: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        changes_list: List[CompareChangeItem] = []

        for ch in changes_raw:
            ct = ch.get('change_type', 'modification')
            cc = ch.get('change_category', 'textual')
            by_type[ct] = by_type.get(ct, 0) + 1
            by_category[cc] = by_category.get(cc, 0) + 1

            # Extract clause number
            clause_num = diff_service.extract_clause_number(
                ch.get('old_content') or ch.get('new_content') or '',
                ch.get('xpath_location')
            )

            changes_list.append(CompareChangeItem(
                change_type=ct,
                change_category=cc,
                section_name=ch.get('section_name'),
                clause_number=clause_num,
                old_content=ch.get('old_content'),
                new_content=ch.get('new_content'),
                xpath_location=ch.get('xpath_location')
            ))

        total_changes = len(changes_list)

        # Determine overall assessment
        additions = by_type.get('addition', 0)
        deletions = by_type.get('deletion', 0)
        if total_changes == 0:
            assessment = 'neutral'
        elif deletions > additions * 2:
            assessment = 'unfavorable'
        elif additions > deletions * 2:
            assessment = 'favorable'
        else:
            assessment = 'mixed'

        summary = f"Обнаружено {total_changes} изменений: {by_type.get('addition', 0)} добавлений, {by_type.get('deletion', 0)} удалений, {by_type.get('modification', 0)} модификаций."

        # Save changes to DB
        for ch_item in changes_list:
            db_change = ContractChange(
                from_version_id=from_version.id,
                to_version_id=to_version.id,
                change_type=ch_item.change_type,
                change_category=ch_item.change_category,
                xpath_location=ch_item.xpath_location,
                section_name=ch_item.section_name,
                clause_number=ch_item.clause_number,
                old_content=ch_item.old_content,
                new_content=ch_item.new_content,
                detected_by='DocumentDiffService',
                confidence_score=1.0
            )
            db.add(db_change)

        # Save analysis result
        analysis_result = ChangeAnalysisResult(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            total_changes=total_changes,
            by_type=by_type,
            by_category=by_category,
            overall_assessment=assessment,
            executive_summary=summary,
            analyzed_by='DocumentDiffService'
        )
        db.add(analysis_result)
        db.commit()

        logger.info(f"Compared versions {from_version.version_number} vs {to_version.version_number} for contract {contract_id}: {total_changes} changes")

        return CompareResultResponse(
            total_changes=total_changes,
            by_type=by_type,
            by_category=by_category,
            overall_assessment=assessment,
            changes=changes_list,
            executive_summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing versions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {str(e)}")
