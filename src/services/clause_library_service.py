"""
Clause Library Service

Manages extraction, storage, and retrieval of contract clauses.
Integrates with ClauseExtractor for extraction and stores results in DB.
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from loguru import logger

from src.models.clause_models import ExtractedClause


# Severity mapping for risk levels
SEVERITY_MAP = {
    'critical': 1.0,
    'high': 0.8,
    'significant': 0.6,
    'medium': 0.4,
    'minor': 0.2,
    'low': 0.1,
    'none': 0.0,
}


class ClauseLibraryService:
    """Service for managing the clause library"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def save_clauses(
        self,
        contract_id: str,
        clauses: List[Dict],
        analyses: Optional[List[Dict]] = None
    ) -> List[ExtractedClause]:
        """
        Save extracted clauses and their analyses to the database.

        Args:
            contract_id: Contract ID
            clauses: Result from ClauseExtractor.extract_clauses()
            analyses: Optional batch analysis JSON from LLM agent

        Returns:
            List of created ExtractedClause records
        """
        # Build analysis lookup by clause number
        analysis_map: Dict[int, Dict] = {}
        if analyses:
            for analysis in analyses:
                clause_num = analysis.get('clause_number')
                if clause_num is not None:
                    analysis_map[clause_num] = analysis

        # Delete existing clauses for this contract (re-analysis)
        self.db.query(ExtractedClause).filter(
            ExtractedClause.contract_id == contract_id
        ).delete()

        saved = []
        for clause in clauses:
            clause_number = clause.get('number', 0)
            analysis = analysis_map.get(clause_number, {})

            # Determine risk level from analysis
            risk_level = self._determine_risk_level(analysis)
            severity_score = SEVERITY_MAP.get(risk_level, 0.0)

            # Extract tags from clause type and analysis
            tags = self._extract_tags(clause, analysis)

            extracted = ExtractedClause(
                contract_id=contract_id,
                clause_number=clause_number,
                clause_type=clause.get('type', 'general'),
                title=clause.get('title', '')[:500],
                text=clause.get('text', '')[:2000],
                xpath_location=clause.get('xpath') or clause.get('path', ''),
                analysis_json=json.dumps(analysis, ensure_ascii=False) if analysis else None,
                risk_level=risk_level,
                severity_score=severity_score,
                tags=json.dumps(tags, ensure_ascii=False),
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(extracted)
            saved.append(extracted)

        try:
            self.db.commit()
            logger.info(f"Saved {len(saved)} clauses for contract {contract_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving clauses for contract {contract_id}: {e}")
            raise

        return saved

    def get_library(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get paginated clause library with optional filters.

        Args:
            filters: Dict with optional keys: clause_type, risk_level, contract_id
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Dict with clauses list, total count, page info
        """
        query = self.db.query(ExtractedClause)

        if filters:
            if filters.get('clause_type'):
                query = query.filter(ExtractedClause.clause_type == filters['clause_type'])
            if filters.get('risk_level'):
                query = query.filter(ExtractedClause.risk_level == filters['risk_level'])
            if filters.get('contract_id'):
                query = query.filter(ExtractedClause.contract_id == filters['contract_id'])

        total = query.count()
        clauses = (
            query
            .order_by(desc(ExtractedClause.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            'clauses': [self._clause_to_dict(c) for c in clauses],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }

    def get_clause(self, clause_id: str) -> Optional[Dict]:
        """Get clause details by ID"""
        clause = self.db.query(ExtractedClause).filter(
            ExtractedClause.id == clause_id
        ).first()

        if not clause:
            return None

        result = self._clause_to_dict(clause)
        # Include full analysis for detail view
        if clause.analysis_json:
            try:
                result['analysis'] = json.loads(clause.analysis_json)
            except json.JSONDecodeError:
                result['analysis'] = None
        return result

    def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get clause library statistics (filtered by user's contracts if user_id provided)"""
        from src.models.database import Contract

        base = self.db.query(ExtractedClause)
        if user_id:
            base = base.join(Contract, Contract.id == ExtractedClause.contract_id).filter(
                Contract.assigned_to == user_id
            )

        total = base.with_entities(func.count(ExtractedClause.id)).scalar() or 0

        # Count by type
        type_stats = (
            base.with_entities(
                ExtractedClause.clause_type,
                func.count(ExtractedClause.id)
            )
            .group_by(ExtractedClause.clause_type)
            .all()
        )

        # Count by risk level
        risk_stats = (
            base.with_entities(
                ExtractedClause.risk_level,
                func.count(ExtractedClause.id)
            )
            .group_by(ExtractedClause.risk_level)
            .all()
        )

        # Average severity score
        avg_severity = base.with_entities(
            func.avg(ExtractedClause.severity_score)
        ).scalar() or 0.0

        # Contracts with clauses
        contracts_count = base.with_entities(
            func.count(func.distinct(ExtractedClause.contract_id))
        ).scalar() or 0

        return {
            'total_clauses': total,
            'contracts_with_clauses': contracts_count,
            'average_severity': round(float(avg_severity), 3),
            'by_type': {t: c for t, c in type_stats},
            'by_risk_level': {r or 'none': c for r, c in risk_stats}
        }

    def search(
        self,
        query: str,
        clause_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search clauses by text content.

        Args:
            query: Search text (LIKE matching)
            clause_type: Optional filter by type
            page: Page number
            page_size: Items per page
            user_id: Filter by contract owner (None = all, for admins)
        """
        from src.models.database import Contract

        safe_q = query.replace('%', r'\%').replace('_', r'\_')
        db_query = self.db.query(ExtractedClause).filter(
            ExtractedClause.text.ilike(f'%{safe_q}%', escape='\\')
        )

        # Security: non-admins can only search their own contracts' clauses
        if user_id:
            db_query = db_query.join(
                Contract, Contract.id == ExtractedClause.contract_id
            ).filter(Contract.assigned_to == user_id)

        if clause_type:
            db_query = db_query.filter(ExtractedClause.clause_type == clause_type)

        total = db_query.count()
        clauses = (
            db_query
            .order_by(desc(ExtractedClause.severity_score))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            'clauses': [self._clause_to_dict(c) for c in clauses],
            'total': total,
            'page': page,
            'page_size': page_size,
            'query': query
        }

    def create_clause(self, data: Dict[str, Any]) -> Dict:
        """Create a new clause manually."""
        tags = data.get('tags', [])
        risk_level = data.get('risk_level', 'none')

        clause = ExtractedClause(
            contract_id=data.get('contract_id'),
            clause_number=data.get('clause_number', 0),
            clause_type=data.get('clause_type', 'general'),
            title=data.get('title', '')[:500],
            text=data.get('text', '')[:5000],
            xpath_location='',
            analysis_json=None,
            risk_level=risk_level,
            severity_score=SEVERITY_MAP.get(risk_level, 0.0),
            tags=json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else tags,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(clause)
        try:
            self.db.commit()
            self.db.refresh(clause)
            return self._clause_to_dict(clause)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating clause: {e}")
            raise

    def update_clause(self, clause_id: str, data: Dict[str, Any]) -> Optional[Dict]:
        """Update clause fields (title, text, clause_type, risk_level, tags)."""
        clause = self.db.query(ExtractedClause).filter(
            ExtractedClause.id == clause_id
        ).first()

        if not clause:
            return None

        allowed_fields = {'title', 'text', 'clause_type', 'risk_level'}
        for field in allowed_fields:
            if field in data:
                setattr(clause, field, data[field])

        if 'tags' in data:
            clause.tags = json.dumps(data['tags'], ensure_ascii=False) if isinstance(data['tags'], list) else data['tags']

        if 'risk_level' in data:
            clause.severity_score = SEVERITY_MAP.get(data['risk_level'], 0.0)

        try:
            self.db.commit()
            self.db.refresh(clause)
            return self._clause_to_dict(clause)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating clause {clause_id}: {e}")
            raise

    def delete_clause(self, clause_id: str) -> bool:
        """Delete a clause by ID. Returns True if deleted."""
        deleted = self.db.query(ExtractedClause).filter(
            ExtractedClause.id == clause_id
        ).delete()

        try:
            self.db.commit()
            return deleted > 0
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting clause {clause_id}: {e}")
            raise

    # ==================== Private Methods ====================

    def _determine_risk_level(self, analysis: Dict) -> str:
        """Determine risk level from LLM analysis"""
        if not analysis:
            return 'none'

        risks = analysis.get('risks', [])
        if not risks:
            return 'none'

        # Use the highest severity among risks
        severity_order = ['critical', 'high', 'significant', 'medium', 'minor', 'low']
        max_severity = 'low'

        for risk in risks:
            severity = risk.get('severity', 'low').lower()
            if severity in severity_order:
                if severity_order.index(severity) < severity_order.index(max_severity):
                    max_severity = severity

        # Map to simplified risk levels
        level_map = {
            'critical': 'critical',
            'high': 'high',
            'significant': 'high',
            'medium': 'medium',
            'minor': 'low',
            'low': 'low',
        }
        return level_map.get(max_severity, 'none')

    def _extract_tags(self, clause: Dict, analysis: Dict) -> List[str]:
        """Extract tags from clause and analysis data"""
        tags = []

        # Add clause type as tag
        clause_type = clause.get('type', '')
        if clause_type:
            tags.append(clause_type)

        # Add risk types from analysis
        for risk in analysis.get('risks', []):
            risk_type = risk.get('risk_type', '')
            if risk_type and risk_type not in tags:
                tags.append(risk_type)

        # Add recommendation categories
        for rec in analysis.get('recommendations', []):
            category = rec.get('category', '')
            if category and category not in tags:
                tags.append(category)

        return tags

    def _clause_to_dict(self, clause: ExtractedClause) -> Dict:
        """Convert ExtractedClause to dictionary"""
        tags = []
        if clause.tags:
            try:
                tags = json.loads(clause.tags)
            except json.JSONDecodeError:
                pass

        return {
            'id': clause.id,
            'contract_id': clause.contract_id,
            'clause_number': clause.clause_number,
            'clause_type': clause.clause_type,
            'title': clause.title,
            'text': clause.text,
            'xpath_location': clause.xpath_location,
            'risk_level': clause.risk_level,
            'severity_score': clause.severity_score,
            'tags': tags,
            'created_at': clause.created_at.isoformat() if clause.created_at else None
        }
