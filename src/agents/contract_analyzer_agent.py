# -*- coding: utf-8 -*-
"""
Contract Analyzer Agent - Deep analysis of contracts with risk identification
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from lxml import etree
from loguru import logger

from .base_agent import BaseAgent, AgentResult
from ..services.llm_gateway import LLMGateway
from ..services.template_manager import TemplateManager
from ..services.counterparty_service import CounterpartyService
from ..models.analyzer_models import (
    ContractRisk, ContractRecommendation, ContractAnnotation,
    ContractSuggestedChange
)
from ..models.database import Contract, AnalysisResult

# Optional RAG import
try:
    from ..services.rag_system import RAGSystem
except ImportError:
    RAGSystem = None


class ContractAnalyzerAgent(BaseAgent):
    """
    Agent for deep contract analysis

    Capabilities:
    - Maximum depth analysis (all risk types)
    - RAG integration (analogues + precedents + legal norms)
    - Risk identification (financial, legal, operational, reputational)
    - Automatic change suggestions with LLM
    - Template comparison
    - Counterparty checking (optional)
    - Dispute probability prediction
    - Annotated XML generation
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db_session,
        template_manager: Optional[TemplateManager] = None,
        rag_system: Optional['RAGSystem'] = None,
        counterparty_service: Optional[CounterpartyService] = None
    ):
        super().__init__(llm_gateway, db_session)
        self.template_manager = template_manager or TemplateManager(db_session)
        self.rag_system = rag_system
        self.counterparty_service = counterparty_service or CounterpartyService()

    def get_name(self) -> str:
        return "ContractAnalyzerAgent"

    def get_system_prompt(self) -> str:
        return """You are a contract analysis expert specializing in Russian contract law.

Your task is to perform deep analysis of contracts and identify:
1. RISKS (financial, legal, operational, reputational)
   - Severity: critical, significant, minor
   - Probability: high, medium, low
   - Consequences: qualitative assessment (no monetary values)

2. RECOMMENDATIONS for contract improvement
   - Priority: critical, high, medium, low
   - Category: legal_compliance, risk_mitigation, financial_optimization, etc.
   - Expected benefit and implementation complexity

3. SUGGESTED CHANGES (automatic via LLM)
   - Original text and suggested replacement
   - Issue description and reasoning
   - Legal basis (references to laws, articles)
   - Change type: addition, modification, deletion, clarification

4. DISPUTE PROBABILITY PREDICTION
   - Overall score and reasoning
   - Specific clauses that may lead to disputes

5. ANNOTATIONS for document sections
   - Type: risk, warning, info, suggestion
   - Location via xpath
   - Related risks/recommendations

Always provide structured JSON output with all identified issues.
Use RAG sources (precedents, legal norms, analogues) to support your analysis.
"""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute contract analysis

        Expected state:
        - contract_id: ID of contract to analyze
        - parsed_xml: Parsed XML content
        - metadata: Contract metadata
        - check_counterparty: Optional flag to check counterparty info

        Returns:
        - analysis_id: ID of created analysis
        - risks: List of identified risks
        - recommendations: List of recommendations
        - suggested_changes: List of suggested changes
        - annotations: List of annotations
        - dispute_probability: Dispute prediction
        - counterparty_data: Optional counterparty check results
        - next_action: 'review_queue' or 'export'
        """
        try:
            contract_id = state.get('contract_id')
            parsed_xml = state.get('parsed_xml')
            metadata = state.get('metadata', {})
            check_counterparty = state.get('check_counterparty', False)

            if not contract_id or not parsed_xml:
                return AgentResult(
                    success=False,
                    data={},
                    error="Missing contract_id or parsed_xml"
                )

            logger.info(f"Starting analysis for contract {contract_id}")

            # 1. Get contract from DB
            contract = self.db.query(Contract).filter(
                Contract.id == contract_id
            ).first()

            if not contract:
                return AgentResult(
                    success=False,
                    data={},
                    error=f"Contract {contract_id} not found"
                )

            # 2. Create analysis result record
            analysis = self._create_analysis_record(contract)

            # 3. Extract contract structure
            structure = self._extract_structure(parsed_xml)

            # 4. Optional: Check counterparty
            counterparty_data = None
            if check_counterparty:
                counterparty_data = self._check_counterparties(parsed_xml, metadata)

            # 5. Analyze with RAG context
            rag_context = self._get_rag_context(parsed_xml, metadata)

            # 6. Identify risks
            risks = self._identify_risks(
                parsed_xml, structure, rag_context, counterparty_data
            )
            self._save_risks(analysis.id, contract.id, risks)

            # 7. Generate recommendations
            recommendations = self._generate_recommendations(
                parsed_xml, structure, risks, rag_context
            )
            self._save_recommendations(analysis.id, contract.id, recommendations)

            # 8. Generate suggested changes (LLM)
            suggested_changes = self._generate_suggested_changes(
                parsed_xml, structure, risks, recommendations, rag_context
            )
            self._save_suggested_changes(analysis.id, contract.id, suggested_changes)

            # 9. Generate annotations
            annotations = self._generate_annotations(
                risks, recommendations, suggested_changes
            )
            self._save_annotations(analysis.id, contract.id, annotations)

            # 10. Predict dispute probability
            dispute_prediction = self._predict_disputes(
                parsed_xml, risks, rag_context
            )

            # 11. Compare with templates (if available)
            template_comparison = self._compare_with_templates(
                parsed_xml, metadata.get('contract_type')
            )

            # 12. Update analysis record
            analysis.status = 'completed'
            analysis.result_data = {
                'risk_count': len(risks),
                'recommendation_count': len(recommendations),
                'suggested_changes_count': len(suggested_changes),
                'dispute_probability': dispute_prediction.get('score'),
                'template_comparison': template_comparison,
                'counterparty_checked': counterparty_data is not None
            }
            self.db.commit()
            self.db.refresh(analysis)

            # 13. Determine next action
            next_action = self._determine_next_action(risks, dispute_prediction)

            logger.info(f"Analysis completed: {len(risks)} risks, {len(recommendations)} recommendations")

            return AgentResult(
                success=True,
                data={
                    'analysis_id': analysis.id,
                    'contract_id': contract.id,
                    'risks': [self._risk_to_dict(r) for r in risks],
                    'recommendations': [self._recommendation_to_dict(r) for r in recommendations],
                    'suggested_changes': [self._change_to_dict(c) for c in suggested_changes],
                    'annotations': [self._annotation_to_dict(a) for a in annotations],
                    'dispute_prediction': dispute_prediction,
                    'template_comparison': template_comparison,
                    'counterparty_data': counterparty_data
                },
                next_action=next_action,
                message=f"Analysis completed: {len(risks)} risks identified, {len(recommendations)} recommendations"
            )

        except Exception as e:
            logger.error(f"Contract analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return AgentResult(
                success=False,
                data={},
                error=str(e)
            )

    def _create_analysis_record(self, contract: Contract) -> AnalysisResult:
        """Create analysis result record"""
        analysis = AnalysisResult(
            contract_id=contract.id,
            status='in_progress',
            result_data={}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def _extract_structure(self, xml_content: str) -> Dict[str, Any]:
        """Extract contract structure for analysis"""
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
            root = tree

            structure = {
                'sections': [],
                'parties': [],
                'price_info': {},
                'term_info': {},
                'payment_terms': [],
                'liability_clauses': [],
                'dispute_resolution': {}
            }

            # Extract parties
            parties = root.findall('.//party')
            for party in parties:
                party_info = {
                    'role': party.get('role', 'unknown'),
                    'name': party.findtext('name', ''),
                    'inn': party.findtext('inn', ''),
                    'xpath': f'//{party.tag}[@role="{party.get("role", "")}"]'
                }
                structure['parties'].append(party_info)

            # Extract price info
            price_elem = root.find('.//price')
            if price_elem is not None:
                structure['price_info'] = {
                    'amount': price_elem.findtext('amount', ''),
                    'currency': price_elem.findtext('currency', 'RUB'),
                    'xpath': f'//{price_elem.tag}'
                }

            # Extract term info
            term_elem = root.find('.//term')
            if term_elem is not None:
                structure['term_info'] = {
                    'start': term_elem.findtext('start', ''),
                    'end': term_elem.findtext('end', ''),
                    'xpath': f'//{term_elem.tag}'
                }

            # Extract all sections
            for elem in root.iter():
                if elem.tag not in ['contract', 'party', 'price', 'term']:
                    structure['sections'].append({
                        'tag': elem.tag,
                        'text': elem.text or '',
                        'xpath': f'//{elem.tag}'
                    })

            return structure

        except Exception as e:
            logger.error(f"Structure extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _check_counterparties(
        self, xml_content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check counterparty information via APIs"""
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            parties = root.findall('.//party')

            results = {}
            for party in parties:
                inn = party.findtext('inn', '').strip()
                name = party.findtext('name', '')

                if inn:
                    logger.info(f"Checking counterparty: {name} (INN: {inn})")
                    check_result = self.counterparty_service.check_counterparty(
                        inn=inn,
                        check_bankruptcy=True
                    )
                    results[name] = check_result

            return results

        except Exception as e:
            logger.error(f"Counterparty check failed: {e}")
            return {}

    def _get_rag_context(
        self, xml_content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get RAG context (analogues + precedents + legal norms)"""
        if not self.rag_system:
            return {'sources': [], 'context': ''}

        try:
            # Extract key terms for RAG query
            contract_type = metadata.get('contract_type', 'unknown')
            subject = metadata.get('subject', '')

            query = f"Договор {contract_type}: {subject}"

            # Search RAG
            results = self.rag_system.search(
                query=query,
                n_results=10,
                filter_metadata={'type': ['analogue', 'precedent', 'legal_norm']}
            )

            context = "\n\n".join([
                f"[{r['metadata'].get('type', 'unknown')}] {r['text']}"
                for r in results
            ])

            return {
                'sources': results,
                'context': context
            }

        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return {'sources': [], 'context': ''}

    def _identify_risks(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]]
    ) -> List[ContractRisk]:
        """Identify contract risks using LLM"""
        try:
            # Prepare prompt
            prompt = self._build_risk_identification_prompt(
                xml_content, structure, rag_context, counterparty_data
            )

            # Call LLM
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            # Parse JSON response
            risks_data = json.loads(response)

            # Convert to ContractRisk objects
            risks = []
            for risk_dict in risks_data.get('risks', []):
                risk = ContractRisk(
                    risk_type=risk_dict.get('risk_type', 'legal'),
                    severity=risk_dict.get('severity', 'minor'),
                    probability=risk_dict.get('probability'),
                    title=risk_dict.get('title', ''),
                    description=risk_dict.get('description', ''),
                    consequences=risk_dict.get('consequences'),
                    xpath_location=risk_dict.get('xpath_location'),
                    section_name=risk_dict.get('section_name'),
                    rag_sources=risk_dict.get('rag_sources', [])
                )
                risks.append(risk)

            return risks

        except Exception as e:
            logger.error(f"Risk identification failed: {e}")
            return []

    def _build_risk_identification_prompt(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for risk identification"""
        prompt = "Analyze this contract and identify ALL risks.\n\n"
        prompt += "CONTRACT XML:\n"
        prompt += xml_content[:5000]
        prompt += "\n\n"

        prompt += "CONTRACT STRUCTURE:\n"
        prompt += json.dumps(structure, ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "RELEVANT LEGAL CONTEXT (from RAG):\n"
            prompt += rag_context['context'][:3000]
            prompt += "\n\n"

        if counterparty_data:
            prompt += "COUNTERPARTY CHECK RESULTS:\n"
            prompt += json.dumps(counterparty_data, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        prompt += """Identify ALL risks in these categories:
- financial (price, payment, penalties)
- legal (compliance, validity, enforceability)
- operational (execution, delivery, quality)
- reputational (brand, relationships)

For each risk, provide:
{
  "risks": [
    {
      "risk_type": "financial|legal|operational|reputational",
      "severity": "critical|significant|minor",
      "probability": "high|medium|low",
      "title": "Short title",
      "description": "Detailed description",
      "consequences": "Qualitative consequences (no monetary)",
      "xpath_location": "XPath to problem section",
      "section_name": "Section name",
      "rag_sources": ["Source 1", "Source 2"]
    }
  ]
}

Return ONLY valid JSON, no additional text."""

        return prompt

    def _generate_recommendations(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> List[ContractRecommendation]:
        """Generate recommendations based on risks"""
        try:
            prompt = "Based on identified risks, generate recommendations.\n\n"

            prompt += "IDENTIFIED RISKS:\n"
            risks_summary = [
                {
                    'id': i,
                    'type': r.risk_type,
                    'severity': r.severity,
                    'title': r.title,
                    'description': r.description
                }
                for i, r in enumerate(risks)
            ]
            prompt += json.dumps(risks_summary, ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "LEGAL CONTEXT:\n"
                prompt += rag_context['context'][:2000]
                prompt += "\n\n"

            prompt += """Generate recommendations for each risk.

Return JSON:
{
  "recommendations": [
    {
      "category": "legal_compliance|risk_mitigation|financial_optimization|etc",
      "priority": "critical|high|medium|low",
      "title": "Short title",
      "description": "What to do",
      "reasoning": "Why this recommendation",
      "expected_benefit": "Expected outcome",
      "related_risk_id": 0,
      "implementation_complexity": "easy|medium|hard"
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            recommendations_data = json.loads(response)

            recommendations = []
            for rec_dict in recommendations_data.get('recommendations', []):
                recommendation = ContractRecommendation(
                    category=rec_dict.get('category', 'general'),
                    priority=rec_dict.get('priority', 'medium'),
                    title=rec_dict.get('title', ''),
                    description=rec_dict.get('description', ''),
                    reasoning=rec_dict.get('reasoning'),
                    expected_benefit=rec_dict.get('expected_benefit'),
                    implementation_complexity=rec_dict.get('implementation_complexity')
                )
                recommendations.append(recommendation)

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    def _generate_suggested_changes(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any]
    ) -> List[ContractSuggestedChange]:
        """Generate automatic suggested changes via LLM"""
        try:
            prompt = "Generate specific text changes to fix identified risks.\n\n"

            prompt += "RISKS:\n"
            prompt += json.dumps([
                {'id': i, 'title': r.title, 'description': r.description, 'xpath': r.xpath_location}
                for i, r in enumerate(risks)
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            prompt += "CONTRACT SECTIONS:\n"
            prompt += json.dumps(structure.get('sections', [])[:20], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "LEGAL REFERENCES:\n"
                prompt += rag_context['context'][:2000]
                prompt += "\n\n"

            prompt += """For each risk that can be fixed by changing contract text, provide:

{
  "changes": [
    {
      "xpath_location": "XPath to section",
      "section_name": "Section name",
      "original_text": "Current problematic text",
      "suggested_text": "Improved version",
      "change_type": "addition|modification|deletion|clarification",
      "issue": "What's the problem",
      "reasoning": "Why this change fixes it",
      "legal_basis": "Reference to law/article if applicable",
      "related_risk_id": 0
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )

            changes_data = json.loads(response)

            changes = []
            for change_dict in changes_data.get('changes', []):
                change = ContractSuggestedChange(
                    xpath_location=change_dict.get('xpath_location', ''),
                    section_name=change_dict.get('section_name'),
                    original_text=change_dict.get('original_text', ''),
                    suggested_text=change_dict.get('suggested_text', ''),
                    change_type=change_dict.get('change_type'),
                    issue=change_dict.get('issue', ''),
                    reasoning=change_dict.get('reasoning', ''),
                    legal_basis=change_dict.get('legal_basis'),
                    status='pending'
                )
                changes.append(change)

            return changes

        except Exception as e:
            logger.error(f"Suggested changes generation failed: {e}")
            return []

    def _generate_annotations(
        self,
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        suggested_changes: List[ContractSuggestedChange]
    ) -> List[ContractAnnotation]:
        """Generate annotations for document sections"""
        annotations = []

        for risk in risks:
            if risk.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=risk.xpath_location,
                    section_name=risk.section_name,
                    annotation_type='risk' if risk.severity == 'critical' else 'warning',
                    content=f"{risk.title}: {risk.description}",
                    highlight_color='red' if risk.severity == 'critical' else 'yellow'
                )
                annotations.append(annotation)

        for change in suggested_changes:
            if change.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=change.xpath_location,
                    section_name=change.section_name,
                    annotation_type='suggestion',
                    content=f"Предложение: {change.issue}",
                    highlight_color='yellow'
                )
                annotations.append(annotation)

        return annotations

    def _predict_disputes(
        self,
        xml_content: str,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict dispute probability using LLM"""
        try:
            prompt = "Predict the probability of disputes arising from this contract.\n\n"

            prompt += "IDENTIFIED RISKS:\n"
            prompt += json.dumps([
                {'type': r.risk_type, 'severity': r.severity, 'title': r.title}
                for r in risks
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "PRECEDENTS:\n"
                prompt += rag_context['context'][:1500]
                prompt += "\n\n"

            prompt += """Analyze dispute probability.

Return JSON:
{
  "overall_score": 0-100,
  "level": "low|medium|high|critical",
  "reasoning": "Why this score",
  "dispute_prone_clauses": [
    {
      "clause": "Clause description",
      "reason": "Why disputes may arise",
      "probability": "low|medium|high"
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            return json.loads(response)

        except Exception as e:
            logger.error(f"Dispute prediction failed: {e}")
            return {
                'overall_score': 50,
                'level': 'medium',
                'reasoning': 'Analysis failed',
                'dispute_prone_clauses': []
            }

    def _compare_with_templates(
        self, xml_content: str, contract_type: Optional[str]
    ) -> Dict[str, Any]:
        """Compare contract with templates"""
        if not contract_type:
            return {'compared': False, 'reason': 'No contract type specified'}

        try:
            template = self.template_manager.get_template(contract_type)

            if not template:
                return {'compared': False, 'reason': f'No template for type {contract_type}'}

            root = etree.fromstring(xml_content.encode('utf-8'))
            template_root = etree.fromstring(template.xml_content.encode('utf-8'))

            contract_tags = set([elem.tag for elem in root.iter()])
            template_tags = set([elem.tag for elem in template_root.iter()])

            missing_sections = template_tags - contract_tags
            extra_sections = contract_tags - template_tags

            return {
                'compared': True,
                'template_name': template.name,
                'template_version': template.version,
                'missing_sections': list(missing_sections),
                'extra_sections': list(extra_sections),
                'match_percentage': len(contract_tags & template_tags) / len(template_tags) * 100 if template_tags else 0
            }

        except Exception as e:
            logger.error(f"Template comparison failed: {e}")
            return {'compared': False, 'reason': str(e)}

    def _determine_next_action(
        self, risks: List[ContractRisk], dispute_prediction: Dict[str, Any]
    ) -> str:
        """Determine next action based on analysis results"""
        has_critical = any(r.severity == 'critical' for r in risks)
        high_dispute_risk = dispute_prediction.get('level') in ['high', 'critical']

        if has_critical or high_dispute_risk:
            return 'review_queue'

        return 'export'

    def _save_risks(self, analysis_id: str, contract_id: str, risks: List[ContractRisk]):
        """Save risks to database"""
        for risk in risks:
            risk.analysis_id = analysis_id
            risk.contract_id = contract_id
            self.db.add(risk)
        self.db.commit()

    def _save_recommendations(
        self, analysis_id: str, contract_id: str, recommendations: List[ContractRecommendation]
    ):
        """Save recommendations to database"""
        for rec in recommendations:
            rec.analysis_id = analysis_id
            rec.contract_id = contract_id
            self.db.add(rec)
        self.db.commit()

    def _save_suggested_changes(
        self, analysis_id: str, contract_id: str, changes: List[ContractSuggestedChange]
    ):
        """Save suggested changes to database"""
        for change in changes:
            change.analysis_id = analysis_id
            change.contract_id = contract_id
            self.db.add(change)
        self.db.commit()

    def _save_annotations(
        self, analysis_id: str, contract_id: str, annotations: List[ContractAnnotation]
    ):
        """Save annotations to database"""
        for annotation in annotations:
            annotation.analysis_id = analysis_id
            annotation.contract_id = contract_id
            self.db.add(annotation)
        self.db.commit()

    def _risk_to_dict(self, risk: ContractRisk) -> Dict[str, Any]:
        """Convert ContractRisk to dict"""
        return {
            'id': risk.id,
            'risk_type': risk.risk_type,
            'severity': risk.severity,
            'probability': risk.probability,
            'title': risk.title,
            'description': risk.description,
            'consequences': risk.consequences,
            'xpath_location': risk.xpath_location,
            'section_name': risk.section_name
        }

    def _recommendation_to_dict(self, rec: ContractRecommendation) -> Dict[str, Any]:
        """Convert ContractRecommendation to dict"""
        return {
            'id': rec.id,
            'category': rec.category,
            'priority': rec.priority,
            'title': rec.title,
            'description': rec.description,
            'reasoning': rec.reasoning,
            'expected_benefit': rec.expected_benefit,
            'implementation_complexity': rec.implementation_complexity
        }

    def _change_to_dict(self, change: ContractSuggestedChange) -> Dict[str, Any]:
        """Convert ContractSuggestedChange to dict"""
        return {
            'id': change.id,
            'xpath_location': change.xpath_location,
            'section_name': change.section_name,
            'original_text': change.original_text,
            'suggested_text': change.suggested_text,
            'change_type': change.change_type,
            'issue': change.issue,
            'reasoning': change.reasoning,
            'legal_basis': change.legal_basis,
            'status': change.status
        }

    def _annotation_to_dict(self, annotation: ContractAnnotation) -> Dict[str, Any]:
        """Convert ContractAnnotation to dict"""
        return {
            'id': annotation.id,
            'xpath_location': annotation.xpath_location,
            'section_name': annotation.section_name,
            'annotation_type': annotation.annotation_type,
            'content': annotation.content,
            'highlight_color': annotation.highlight_color
        }


__all__ = ["ContractAnalyzerAgent"]
