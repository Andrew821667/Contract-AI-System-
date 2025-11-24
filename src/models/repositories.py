"""
Repository pattern 4;O @01>BK A 107>9 40==KE
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime
import json

from .database import (
    Template, Contract, AnalysisResult,
    ReviewTask, LegalDocument, ExportLog
)
from .auth_models import User


class BaseRepository:
    """07>2K9 :;0AA @5?>78B>@8O A >1I8<8 <5B>40<8"""

    def __init__(self, db: Session, model):
        self.db = db
        self.model = model

    def get_by_id(self, id: str):
        """>;CG8BL ?> ID"""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, limit: int = 100, offset: int = 0):
        """>;CG8BL 2A5 A ?038=0F859"""
        return self.db.query(self.model).offset(offset).limit(limit).all()

    def create(self, **kwargs):
        """!>740BL =>2CN 70?8AL"""
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: str, **kwargs):
        """1=>28BL 70?8AL"""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance

    def delete(self, id: str):
        """#40;8BL 70?8AL"""
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
        return instance


class UserRepository(BaseRepository):
    """ 5?>78B>@89 4;O @01>BK A ?>;L7>20B5;O<8"""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(self, email: str) -> Optional[User]:
        """>;CG8BL ?>;L7>20B5;O ?> email"""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_role(self, role: str) -> List[User]:
        """>;CG8BL 2A5E ?>;L7>20B5;59 A >?@545;Q==>9 @>;LN"""
        return self.db.query(User).filter(User.role == role, User.active == True).all()

    def get_active_users(self) -> List[User]:
        """>;CG8BL 2A5E 0:B82=KE ?>;L7>20B5;59"""
        return self.db.query(User).filter(User.active == True).all()


class TemplateRepository(BaseRepository):
    """ 5?>78B>@89 4;O @01>BK A H01;>=0<8"""

    def __init__(self, db: Session):
        super().__init__(db, Template)

    def get_by_type(self, contract_type: str, active_only: bool = True) -> List[Template]:
        """>;CG8BL H01;>=K ?> B8?C 4>3>2>@0"""
        query = self.db.query(Template).filter(Template.contract_type == contract_type)
        if active_only:
            query = query.filter(Template.active == True)
        return query.all()

    def get_latest_version(self, contract_type: str) -> Optional[Template]:
        """>;CG8BL ?>A;54=NN 25@A8N H01;>=0 4;O B8?0 4>3>2>@0"""
        return self.db.query(Template).filter(
            Template.contract_type == contract_type,
            Template.active == True
        ).order_by(desc(Template.version)).first()

    def get_active_templates(self) -> List[Template]:
        """>;CG8BL 2A5 0:B82=K5 H01;>=K"""
        return self.db.query(Template).filter(Template.active == True).all()


class ContractRepository(BaseRepository):
    """ 5?>78B>@89 4;O @01>BK A 4>3>2>@0<8"""

    def __init__(self, db: Session):
        super().__init__(db, Contract)

    def get_by_status(self, status: str) -> List[Contract]:
        """>;CG8BL 4>3>2>@K ?> AB0BCAC"""
        return self.db.query(Contract).filter(Contract.status == status).all()

    def get_by_risk_level(self, risk_level: str) -> List[Contract]:
        """>;CG8BL 4>3>2>@K ?> C@>2=N @8A:0"""
        return self.db.query(Contract).filter(Contract.risk_level == risk_level).all()

    def get_assigned_to_user(self, user_id: str) -> List[Contract]:
        """>;CG8BL 4>3>2>@K, =07=0G5==K5 ?>;L7>20B5;N"""
        return self.db.query(Contract).filter(Contract.assigned_to == user_id).all()

    def get_recent(self, limit: int = 10) -> List[Contract]:
        """>;CG8BL ?>A;54=85 703@C65==K5 4>3>2>@K"""
        return self.db.query(Contract).order_by(desc(Contract.upload_date)).limit(limit).all()

    def update_status(self, contract_id: str, status: str):
        """1=>28BL AB0BCA 4>3>2>@0"""
        return self.update(contract_id, status=status)

    def assign_to_user(self, contract_id: str, user_id: str):
        """07=0G8BL 4>3>2>@ ?>;L7>20B5;N"""
        return self.update(contract_id, assigned_to=user_id)


class AnalysisResultRepository(BaseRepository):
    """ 5?>78B>@89 4;O @57C;LB0B>2 0=0;870"""

    def __init__(self, db: Session):
        super().__init__(db, AnalysisResult)

    def get_by_contract(self, contract_id: str) -> List[AnalysisResult]:
        """>;CG8BL 2A5 0=0;87K 4;O 4>3>2>@0"""
        return self.db.query(AnalysisResult).filter(
            AnalysisResult.contract_id == contract_id
        ).order_by(desc(AnalysisResult.version)).all()

    def get_latest_analysis(self, contract_id: str) -> Optional[AnalysisResult]:
        """>;CG8BL ?>A;54=89 0=0;87 4;O 4>3>2>@0"""
        return self.db.query(AnalysisResult).filter(
            AnalysisResult.contract_id == contract_id
        ).order_by(desc(AnalysisResult.version)).first()

    def create_analysis(self, contract_id: str, analysis_data: Dict[str, Any]):
        """!>740BL =>2K9 @57C;LB0B 0=0;870"""
        # !5@80;87C5< JSON ?>;O
        return self.create(
            contract_id=contract_id,
            entities=json.dumps(analysis_data.get('entities'), ensure_ascii=False),
            compliance_issues=json.dumps(analysis_data.get('compliance_issues'), ensure_ascii=False),
            legal_issues=json.dumps(analysis_data.get('legal_issues'), ensure_ascii=False),
            risks_by_category=json.dumps(analysis_data.get('risks_by_category'), ensure_ascii=False),
            recommendations=json.dumps(analysis_data.get('recommendations'), ensure_ascii=False),
            version=analysis_data.get('version', 1)
        )


class ReviewTaskRepository(BaseRepository):
    """ 5?>78B>@89 4;O 7040G =0 ?@>25@:C"""

    def __init__(self, db: Session):
        super().__init__(db, ReviewTask)

    def get_pending_tasks(self, user_id: Optional[str] = None) -> List[ReviewTask]:
        """>;CG8BL >6840NI85 7040G8"""
        query = self.db.query(ReviewTask).filter(ReviewTask.status == 'pending')
        if user_id:
            query = query.filter(ReviewTask.assigned_to == user_id)
        return query.order_by(ReviewTask.priority, ReviewTask.deadline).all()

    def get_overdue_tasks(self) -> List[ReviewTask]:
        """>;CG8BL ?@>A@>G5==K5 7040G8"""
        return self.db.query(ReviewTask).filter(
            ReviewTask.status != 'completed',
            ReviewTask.deadline < datetime.utcnow()
        ).all()

    def assign_task(self, task_id: str, user_id: str):
        """07=0G8BL 7040GC ?>;L7>20B5;N"""
        return self.update(task_id, assigned_to=user_id, status='in_progress')

    def complete_task(self, task_id: str, decision: str, comments: Optional[str] = None):
        """025@H8BL 7040GC"""
        return self.update(
            task_id,
            status='completed',
            decision=decision,
            comments=comments,
            completed_at=datetime.utcnow()
        )

    def create_task(self, contract_id: str, priority: str = 'normal', deadline: Optional[datetime] = None):
        """!>740BL =>2CN 7040GC =0 ?@>25@:C"""
        return self.create(
            contract_id=contract_id,
            priority=priority,
            deadline=deadline,
            status='pending'
        )


class LegalDocumentRepository(BaseRepository):
    """ 5?>78B>@89 4;O N@848G5A:8E 4>:C<5=B>2"""

    def __init__(self, db: Session):
        super().__init__(db, LegalDocument)

    def get_by_type(self, doc_type: str) -> List[LegalDocument]:
        """>;CG8BL 4>:C<5=BK ?> B8?C"""
        return self.db.query(LegalDocument).filter(
            LegalDocument.doc_type == doc_type,
            LegalDocument.status == 'active'
        ).all()

    def get_by_doc_id(self, doc_id: str) -> Optional[LegalDocument]:
        """>;CG8BL 4>:C<5=B ?> doc_id"""
        return self.db.query(LegalDocument).filter(LegalDocument.doc_id == doc_id).first()

    def get_unvectorized(self, limit: int = 100) -> List[LegalDocument]:
        """>;CG8BL 4>:C<5=BK 157 25:B>@870F88"""
        return self.db.query(LegalDocument).filter(
            LegalDocument.is_vectorized == False,
            LegalDocument.status == 'active'
        ).limit(limit).all()

    def mark_as_vectorized(self, doc_id: str):
        """B<5B8BL 4>:C<5=B :0: 25:B>@87>20==K9"""
        doc = self.get_by_doc_id(doc_id)
        if doc:
            return self.update(doc.id, is_vectorized=True)


class ExportLogRepository(BaseRepository):
    """ 5?>78B>@89 4;O ;>3>2 M:A?>@B0"""

    def __init__(self, db: Session):
        super().__init__(db, ExportLog)

    def get_by_contract(self, contract_id: str) -> List[ExportLog]:
        """>;CG8BL ;>38 M:A?>@B0 4;O 4>3>2>@0"""
        return self.db.query(ExportLog).filter(
            ExportLog.contract_id == contract_id
        ).order_by(desc(ExportLog.exported_at)).all()

    def get_by_user(self, user_id: str, limit: int = 50) -> List[ExportLog]:
        """>;CG8BL ;>38 M:A?>@B0 ?>;L7>20B5;O"""
        return self.db.query(ExportLog).filter(
            ExportLog.exported_by == user_id
        ).order_by(desc(ExportLog.exported_at)).limit(limit).all()

    def log_export(self, contract_id: str, user_id: str, export_type: str, metadata: Optional[Dict] = None):
        """0;>38@>20BL M:A?>@B"""
        return self.create(
            contract_id=contract_id,
            exported_by=user_id,
            export_type=export_type,
            meta_info=json.dumps(metadata, ensure_ascii=False) if metadata else None
        )


# -:A?>@B 2A5E @5?>78B>@852
__all__ = [
    "BaseRepository",
    "UserRepository",
    "TemplateRepository",
    "ContractRepository",
    "AnalysisResultRepository",
    "ReviewTaskRepository",
    "LegalDocumentRepository",
    "ExportLogRepository"
]
