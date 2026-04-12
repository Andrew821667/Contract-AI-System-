# -*- coding: utf-8 -*-
"""
Contract Analyzer Agent - Deep analysis of contracts with risk identification
"""
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from lxml import etree
from loguru import logger

from .base_agent import BaseAgent, AgentResult
from ..services.llm_gateway import LLMGateway
from ..services.template_manager import TemplateManager
from ..services.counterparty_service import CounterpartyService
from ..services.clause_extractor import ClauseExtractor
from ..services.risk_analyzer import RiskAnalyzer
from ..services.recommendation_generator import RecommendationGenerator
from ..services.metadata_analyzer import MetadataAnalyzer
from ..models.analyzer_models import (
    ContractRisk, ContractRecommendation, ContractAnnotation,
    ContractSuggestedChange
)
from ..models.database import Contract, AnalysisResult
from ..utils.contract_types import infer_contract_type_from_xml, is_meaningful_contract_type
from ..utils.xml_security import parse_xml_safely, XMLSecurityError
from ..utils.analysis_filters import (
    should_ignore_future_date_risk,
    should_ignore_required_field,
    should_ignore_signatory_authority_risk,
)
from config.settings import settings

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
        llm_gateway: LLMGateway = None,
        db_session = None,
        template_manager: Optional[TemplateManager] = None,
        rag_system: Optional['RAGSystem'] = None,
        counterparty_service: Optional[CounterpartyService] = None
    ):
        # Если LLM не передан, создаём с быстрой моделью для первого уровня
        if llm_gateway is None:
            from config.settings import settings
            llm_gateway = LLMGateway(model=settings.llm_quick_model)

        super().__init__(llm_gateway, db_session)
        self.template_manager = template_manager or TemplateManager(db_session)
        self.rag_system = rag_system
        self.counterparty_service = counterparty_service or CounterpartyService()

        # Initialize refactored service modules
        self.clause_extractor = ClauseExtractor()
        self.risk_analyzer = RiskAnalyzer(llm_gateway)
        self.recommendation_generator = RecommendationGenerator(
            llm_gateway,
            system_prompt=self.get_system_prompt()
        )
        self.metadata_analyzer = MetadataAnalyzer(
            llm_gateway,
            counterparty_service=self.counterparty_service,
            template_manager=self.template_manager,
            system_prompt=self.get_system_prompt()
        )

    def get_name(self) -> str:
        return "ContractAnalyzerAgent"

    def get_system_prompt(self) -> str:
        return """Ты — эксперт по анализу договоров, специализирующийся на российском договорном праве.
ВАЖНО: Все ответы, описания, рекомендации и комментарии давай ТОЛЬКО на русском языке.

Твоя задача — провести глубокий анализ договора и выявить:
1. РИСКИ (финансовые, юридические, операционные, репутационные)
   - Серьёзность: critical, high, medium, low, info
   - Вероятность: high, medium, low
   - Последствия: качественная оценка (без денежных сумм)

2. РЕКОМЕНДАЦИИ по улучшению договора
   - Приоритет: critical, high, medium, low
   - Категория: legal_compliance, risk_mitigation, financial_optimization и т.д.
   - Ожидаемая польза и сложность реализации

3. ПРЕДЛАГАЕМЫЕ ИЗМЕНЕНИЯ (автоматически через LLM)
   - Оригинальный текст и предлагаемая замена
   - Описание проблемы и обоснование
   - Правовое основание (ссылки на законы, статьи)
   - Тип изменения: addition, modification, deletion, clarification

4. ПРОГНОЗ ВЕРОЯТНОСТИ СПОРОВ
   - Общий балл и обоснование
   - Конкретные пункты, которые могут привести к спорам

5. АННОТАЦИИ к разделам документа
   - Тип: risk, warning, info, suggestion
   - Расположение через xpath
   - Связанные риски/рекомендации

Всегда возвращай структурированный JSON со всеми выявленными проблемами.
Используй RAG-источники (прецеденты, правовые нормы, аналоги) для обоснования анализа.
- Если в договоре не хватает фактических данных для заполнения или редактуры, не выдумывай их.
- Такие случаи помечай как требующие ввода пользователя и формулируй, какие данные нужно запросить.
- Если проблема связана с предметом договора, отдельно различай юридический риск и перечень данных,
  которые нужно получить от пользователя для корректного заполнения предмета.
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
            company_conditions = state.get('company_conditions', [])
            self._clause_analyses = []
            self._required_fields = []
            self._placeholder_clause_ids = set()
            self._full_text_analysis = None
            analysis_context = {
                'analysis_date': metadata.get('analysis_date') or datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat(),
                'analysis_perspective': metadata.get('analysis_perspective') or 'Интересы пользователя',
            }
            self._analysis_context = analysis_context

            if not contract_id or not parsed_xml:
                return AgentResult(
                    success=False,
                    data={},
                    error="Missing contract_id or parsed_xml"
                )

            logger.info(f"Starting analysis for contract {contract_id}")

            contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return AgentResult(
                    success=False,
                    data={},
                    error=f"Contract {contract_id} not found"
                )

            analysis = self._create_analysis_record(contract)
            structure = self.clause_extractor.extract_structure(parsed_xml)
            required_fields = self._extract_required_fields(parsed_xml)

            counterparty_data = None
            if check_counterparty:
                counterparty_data = self.metadata_analyzer.check_counterparties(parsed_xml, metadata)

            def _update_progress(pct: int, msg: str):
                """Update progress in contract meta_info for WS/polling."""
                try:
                    from sqlalchemy.orm.attributes import flag_modified
                    meta = contract.meta_info or {}
                    if not isinstance(meta, dict):
                        import json as _j
                        meta = _j.loads(meta) if meta else {}
                    meta["_progress"] = pct
                    meta["_progress_msg"] = msg
                    contract.meta_info = meta
                    flag_modified(contract, "meta_info")
                    self.db.commit()
                    logger.debug(f"Progress updated: {pct}% - {msg}")
                except Exception as exc:
                    logger.warning(f"Failed to update progress: {exc}")
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

            self._progress_updater = _update_progress

            kb_available = self._has_available_rag_sources()
            if kb_available:
                _update_progress(35, "Поиск контекста в базе знаний...")
            else:
                _update_progress(35, "База знаний пуста, пропускаем поиск контекста...")
            rag_context = self._get_rag_context(parsed_xml, metadata, kb_available=kb_available)
            detected_contract_type = infer_contract_type_from_xml(
                parsed_xml,
                fallback=metadata.get('contract_type') or contract.contract_type,
                file_name=contract.file_name,
            )
            if is_meaningful_contract_type(detected_contract_type):
                contract.contract_type = detected_contract_type
                self.db.commit()
                metadata['contract_type'] = detected_contract_type

            _update_progress(40, "AI анализ: выявление рисков...")
            risks = self._identify_risks(
                parsed_xml,
                structure,
                rag_context,
                counterparty_data,
                company_conditions=company_conditions,
                analysis_context=analysis_context,
            )
            required_fields = list(getattr(self, '_required_fields', required_fields))
            risks = self._filter_placeholder_risks(risks)
            _update_progress(60, f"Найдено {len(risks)} рисков, сохранение...")
            self._save_risks(analysis.id, contract.id, risks)

            _update_progress(65, "Генерация рекомендаций...")
            recommendations = self.recommendation_generator.generate_recommendations(
                risks,
                rag_context,
                company_conditions=company_conditions,
                required_fields=required_fields,
            )
            _update_progress(72, f"Сохранение {len(recommendations)} рекомендаций...")
            self._save_recommendations(analysis.id, contract.id, recommendations)

            _update_progress(78, "Генерация предложений по изменениям...")
            suggested_changes = self.recommendation_generator.generate_suggested_changes(
                parsed_xml, structure, risks, recommendations, rag_context, required_fields=required_fields
            )
            self._save_suggested_changes(analysis.id, contract.id, suggested_changes)

            _update_progress(82, "Создание аннотаций...")
            annotations = self.recommendation_generator.generate_annotations(
                risks, recommendations, suggested_changes
            )
            self._save_annotations(analysis.id, contract.id, annotations)

            _update_progress(88, "Прогноз вероятности споров...")
            dispute_prediction = self.metadata_analyzer.predict_disputes(
                parsed_xml, risks, rag_context
            )

            _update_progress(92, "Сравнение с шаблонами...")
            template_comparison = self.metadata_analyzer.compare_with_templates(
                parsed_xml, metadata.get('contract_type')
            )

            analysis.entities = json.dumps({
                'analysis_context': analysis_context,
                'parties': structure.get('parties', []),
            }, ensure_ascii=False)
            analysis.legal_issues = json.dumps({
                'required_fields': required_fields,
            }, ensure_ascii=False)
            analysis.risks_by_category = json.dumps({
                'risk_count': len(risks),
                'recommendation_count': len(recommendations),
                'suggested_changes_count': len(suggested_changes),
                'dispute_probability': dispute_prediction.get('overall_score', dispute_prediction.get('score')),
                'template_comparison': template_comparison,
                'counterparty_checked': counterparty_data is not None,
                'analysis_date': analysis_context.get('analysis_date'),
                'analysis_perspective': analysis_context.get('analysis_perspective'),
                'required_fields_count': len(required_fields),
            }, ensure_ascii=False)
            self.db.commit()
            self.db.refresh(analysis)

            next_action = self.metadata_analyzer.determine_next_action(risks, dispute_prediction)
            clause_analyses = getattr(self, '_clause_analyses', [])
            full_text_analysis = getattr(self, '_full_text_analysis', None)

            logger.info(f"Analysis completed: {len(risks)} risks, {len(recommendations)} recommendations")

            return AgentResult(
                success=True,
                data={
                    'analysis_id': analysis.id,
                    'contract_id': contract.id,
                    'risks': [self._risk_to_dict(r) for r in risks],
                    'recommendations': [self._recommendation_to_dict(r) for r in recommendations],
                    'required_fields': required_fields,
                    'suggested_changes': [self._change_to_dict(c) for c in suggested_changes],
                    'annotations': [self._annotation_to_dict(a) for a in annotations],
                    'dispute_prediction': dispute_prediction,
                    'template_comparison': template_comparison,
                    'counterparty_data': counterparty_data,
                    'analysis_context': analysis_context,
                    'contract_type': detected_contract_type,
                    'clause_analyses': clause_analyses,
                    'full_text_analysis': full_text_analysis,
                    'disclaimer': 'Результаты AI-анализа носят рекомендательный характер и не являются юридической консультацией. Перед принятием решений проконсультируйтесь с квалифицированным юристом.'
                },
                next_action=next_action,
                metadata={
                    'message': (
                        f"Analysis completed: {len(risks)} risks identified, {len(recommendations)} recommendations, "
                        f"{len(required_fields)} required fields, {len(clause_analyses)} clauses analyzed"
                    )
                }
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
            entities='{}',
            compliance_issues='{}',
            legal_issues='{}',
            risks_by_category='{}',
            recommendations='{}',
            version=1
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def _extract_structure(self, xml_content: str) -> Dict[str, Any]:
        """Extract contract structure for analysis"""
        try:
            tree = parse_xml_safely(xml_content)
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

            # Extract all sections with detailed info
            for elem in root.iter():
                if elem.tag not in ['contract', 'party', 'price', 'term']:
                    text_content = elem.text or ''
                    # Also capture text from child elements
                    full_text = ''.join(elem.itertext()).strip()

                    structure['sections'].append({
                        'tag': elem.tag,
                        'text': text_content,
                        'full_text': full_text,
                        'xpath': f'//{elem.tag}',
                        'attributes': dict(elem.attrib)
                    })

            return structure

        except Exception as e:
            logger.error(f"Structure extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _extract_plain_text(self, xml_content: str) -> str:
        """Convert normalized XML into stable plain text for full-document analysis."""
        try:
            root = parse_xml_safely(xml_content)
            clause_nodes = root.findall('.//clauses/clause')
            chunks: List[str] = []

            if clause_nodes:
                for clause in clause_nodes:
                    title = (clause.findtext('title', '') or '').strip()
                    paragraphs = [
                        ' '.join((paragraph.text or '').split())
                        for paragraph in clause.findall('.//paragraph')
                        if (paragraph.text or '').strip()
                    ]
                    clause_text = '\n'.join(part for part in [title, *paragraphs] if part).strip()
                    if clause_text:
                        chunks.append(clause_text)
                if chunks:
                    return '\n\n'.join(chunks)

            for text in root.itertext():
                cleaned = ' '.join((text or '').split())
                if cleaned:
                    chunks.append(cleaned)
            return '\n'.join(chunks)
        except XMLSecurityError as exc:
            logger.warning(f"Plain text extraction blocked by XML security: {exc}")
            return ''
        except Exception as exc:
            logger.error(f"Plain text extraction failed: {exc}")
            return ''

    def _extract_contract_clauses(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Extract individual contract clauses for detailed analysis
        Разбивает договор на отдельные пункты для детального анализа
        """
        try:
            logger.info("Starting clause extraction from XML...")
            tree = parse_xml_safely(xml_content)
            root = tree

            logger.info(f"Root tag: {root.tag}, children: {len(list(root))}")

            clauses = []
            clause_counter = 1

            # Рекурсивная функция для извлечения пунктов
            def extract_recursive(element, parent_path="", level=0):
                nonlocal clause_counter

                # Пропускаем только contract и metadata на верхнем уровне
                if level == 0 and element.tag in ['contract', 'document', 'root']:
                    logger.info(f"Processing root element: {element.tag}")
                    for child in element:
                        extract_recursive(child, element.tag, level + 1)
                    return

                # Получаем текст элемента
                elem_text = (element.text or '').strip()

                # Собираем весь текст из дочерних элементов
                full_text = ''.join(element.itertext()).strip()

                # Определяем тип пункта
                clause_type = self._determine_clause_type(element.tag, full_text)

                # Путь к пункту
                current_path = f"{parent_path}/{element.tag}" if parent_path else element.tag

                # Если есть содержательный текст - это пункт договора
                # Снижаем порог до 5 символов для захвата коротких пунктов
                if full_text and len(full_text) > 5:
                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': element.tag,
                        'path': current_path,
                        'xpath': current_path,  # Use path instead of getpath
                        'title': self._extract_clause_title(element.tag, full_text),
                        'text': full_text[:2000],  # Ограничиваем текст 2000 символов
                        'type': clause_type,
                        'level': level,
                        'attributes': dict(element.attrib),
                        'children_count': len(list(element))
                    }
                    clauses.append(clause)
                    logger.debug(f"Clause {clause_counter}: {element.tag} - {full_text[:50]}")
                    clause_counter += 1

                    # Если у элемента нет детей - не идём дальше
                    if len(list(element)) == 0:
                        return

                # Рекурсивно обрабатываем дочерние элементы
                for child in element:
                    extract_recursive(child, current_path, level + 1)

            extract_recursive(root)

            logger.info(f"✓ Extracted {len(clauses)} contract clauses for detailed analysis")

            # Если не нашли пунктов - попробуем альтернативный метод
            if len(clauses) == 0:
                logger.warning("No clauses found with standard extraction, trying alternative method...")
                clauses = self._extract_clauses_alternative(xml_content)
                logger.info(f"Alternative method found {len(clauses)} clauses")

            return clauses

        except Exception as e:
            logger.error(f"Clause extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_clauses_alternative(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Alternative method: split contract into sections based on XML structure
        Специально для DocumentParser который создаёт <clauses><clause>...</clause></clauses>
        """
        try:
            tree = parse_xml_safely(xml_content)
            clauses = []

            # СНАЧАЛА пробуем найти <clauses><clause> структуру от DocumentParser
            clauses_container = tree.find('.//clauses')
            if clauses_container is not None:
                logger.info("Found <clauses> container from DocumentParser")
                clause_elements = clauses_container.findall('clause')
                logger.info(f"Found {len(clause_elements)} clause elements")

                for idx, clause_elem in enumerate(clause_elements, 1):
                    # Извлекаем title и content
                    title_elem = clause_elem.find('title')
                    content_elem = clause_elem.find('content')

                    title = title_elem.text if title_elem is not None and title_elem.text else f"Пункт {idx}"

                    # Собираем весь текст из content
                    if content_elem is not None:
                        paragraphs = content_elem.findall('paragraph')
                        full_text = '\n'.join([p.text for p in paragraphs if p.text])
                    else:
                        full_text = ''.join(clause_elem.itertext()).strip()

                    if full_text and len(full_text) > 10:
                        clause = {
                            'id': clause_elem.get('id', f"clause_{idx}"),
                            'number': idx,
                            'tag': 'clause',
                            'path': f"/clauses/clause[{idx}]",
                            'xpath': f"/clauses/clause[{idx}]",  # Use path instead of getpath
                            'title': title,
                            'text': full_text[:2000],
                            'type': clause_elem.get('type', self._determine_clause_type(title, full_text)),
                            'level': 0,
                            'attributes': dict(clause_elem.attrib),
                            'children_count': len(list(clause_elem))
                        }
                        clauses.append(clause)
                        logger.info(f"✓ Extracted clause {idx}: {title[:50]}")

                if len(clauses) > 0:
                    logger.info(f"✅ Successfully extracted {len(clauses)} clauses from DocumentParser format")
                    return clauses[:50]  # Limit to 50

            # FALLBACK: если нет <clauses>, берём все элементы с текстом
            logger.info("No <clauses> found, trying generic element extraction...")
            all_elements = list(tree.iter())
            logger.info(f"Found {len(all_elements)} total XML elements")

            clause_counter = 1
            for elem in all_elements:
                full_text = ''.join(elem.itertext()).strip()

                # Берём элементы с текстом длиннее 10 символов
                if full_text and len(full_text) > 10:
                    # Пропускаем элементы, чей текст полностью совпадает с родителем
                    parent = elem.getparent()
                    if parent is not None:
                        parent_text = ''.join(parent.itertext()).strip()
                        if full_text == parent_text:
                            continue

                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': elem.tag,
                        'path': f"/{elem.tag}",
                        'xpath': f"/{elem.tag}",  # Use path instead of getpath
                        'title': self._extract_clause_title(elem.tag, full_text),
                        'text': full_text[:2000],
                        'type': self._determine_clause_type(elem.tag, full_text),
                        'level': 0,
                        'attributes': dict(elem.attrib),
                        'children_count': len(list(elem))
                    }
                    clauses.append(clause)
                    clause_counter += 1

            return clauses[:50]  # Ограничиваем до 50 пунктов для разумного времени анализа

        except Exception as e:
            logger.error(f"Alternative extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _determine_clause_type(self, tag: str, text: str) -> str:
        """Определяет тип пункта договора"""
        tag_lower = tag.lower()
        text_lower = text.lower()

        if any(word in tag_lower for word in ['price', 'payment', 'cost', 'цена', 'оплата', 'стоимость']):
            return 'financial'
        elif any(word in tag_lower for word in ['term', 'deadline', 'срок', 'период']):
            return 'temporal'
        elif any(word in tag_lower for word in ['party', 'сторон', 'контрагент']):
            return 'parties'
        elif any(word in tag_lower for word in ['liability', 'penalty', 'ответственность', 'штраф', 'пеня']):
            return 'liability'
        elif any(word in tag_lower for word in ['dispute', 'arbitration', 'спор', 'арбитраж']):
            return 'dispute'
        elif any(word in tag_lower for word in ['subject', 'предмет', 'объект']):
            return 'subject'
        elif any(word in tag_lower for word in ['termination', 'расторжение']):
            return 'termination'
        else:
            return 'general'

    def _extract_clause_title(self, tag: str, text: str) -> str:
        """Извлекает заголовок пункта"""
        # Берём первые 100 символов или до первой точки
        lines = text.split('\n')
        first_line = lines[0].strip() if lines else text

        if len(first_line) > 80:
            return first_line[:80] + "..."

        return first_line or tag

    def _check_counterparties(
        self, xml_content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check counterparty information via APIs"""
        try:
            root = parse_xml_safely(xml_content)
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

    def _has_available_rag_sources(self) -> bool:
        """Return True only when there is indexed knowledge to search."""
        try:
            from pathlib import Path
            from ..models.database import LegalDocument

            indexed_docs = self.db.query(LegalDocument).filter(
                LegalDocument.status == 'active',
                LegalDocument.is_vectorized.is_(True)
            ).count()
            if indexed_docs > 0:
                return True

            enhanced_dir = Path("data/chroma_enhanced")
            kb_file = enhanced_dir / "company_kb.json"
            if kb_file.exists() and kb_file.stat().st_size > 2:
                return True

            if enhanced_dir.exists():
                for child in enhanced_dir.iterdir():
                    if child.name.startswith("."):
                        continue
                    if child.is_file() and child.stat().st_size > 0:
                        return True
                    if child.is_dir():
                        return True

            return False
        except Exception as exc:
            logger.warning(f"Failed to inspect knowledge base state: {exc}")
            return False

    def _get_rag_context(
        self, xml_content: str, metadata: Dict[str, Any], kb_available: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get RAG context (analogues + precedents + legal norms) + contract summary"""
        try:
            # Извлекаем базовую информацию о договоре из XML
            from lxml import etree
            tree = parse_xml_safely(xml_content)

            # Извлекаем стороны
            parties = []
            for party in tree.findall('.//party'):
                parties.append({
                    'name': party.findtext('name', 'Не указано'),
                    'role': party.get('role', 'unknown'),
                    'inn': party.findtext('inn', '')
                })

            # Извлекаем тип договора из тега или метаданных
            contract_type = metadata.get('contract_type', 'unknown')
            if contract_type == 'unknown':
                # Пытаемся определить из содержимого
                root_tag = tree.tag if hasattr(tree, 'tag') else 'contract'
                contract_type = root_tag.replace('_', ' ').replace('contract', 'договор')

            # Извлекаем предмет договора
            subject = metadata.get('subject', '')
            if not subject:
                # Ищем в first paragraph или description
                desc_elem = tree.find('.//description')
                if desc_elem is not None and desc_elem.text:
                    subject = desc_elem.text[:200]
                else:
                    subject = "Не указан явно"

            contract_summary = {
                'type': contract_type,
                'parties': parties,
                'subject': subject,
                'party_count': len(parties)
            }

            if kb_available is None:
                kb_available = self._has_available_rag_sources()

            if not kb_available:
                logger.info("Knowledge base is empty, skipping RAG lookup")
                return {
                    'sources': [],
                    'context': '',
                    'contract_summary': contract_summary
                }

            # Search RAG if available
            rag_results = []
            rag_context = ""

            if self.rag_system:
                query = f"Договор {contract_type}: {subject}"
                rag_results = self.rag_system.search(
                    query=query,
                    n_results=10,
                    filter_metadata={'type': ['analogue', 'precedent', 'legal_norm']}
                )
                rag_context = "\n\n".join([
                    f"[{r['metadata'].get('type', 'unknown')}] {r['text']}"
                    for r in rag_results
                ])

            # Дополняем контекст из admin-базы знаний (laws + case_law)
            try:
                from src.services.admin_rag_retriever import get_legal_context, has_legal_docs
                if has_legal_docs():
                    query = f"Договор {contract_type}: {subject}"
                    admin_context = get_legal_context(
                        query=query,
                        collections=["laws", "case_law"],
                        n_results=3,
                        max_chars=2000,
                    )
                    if admin_context:
                        rag_context = (rag_context + "\n\n" + admin_context).strip() if rag_context else admin_context
                        logger.info("Admin KB: добавлен правовой контекст из базы знаний")
            except Exception as admin_kb_err:
                logger.debug(f"Admin KB lookup skipped: {admin_kb_err}")

            return {
                'sources': rag_results,
                'context': rag_context,
                'contract_summary': contract_summary
            }

        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            # Возвращаем минимальный контекст
            return {
                'sources': [],
                'context': '',
                'contract_summary': {
                    'type': metadata.get('contract_type', 'неизвестный'),
                    'parties': [],
                    'subject': metadata.get('subject', 'не указан')
                }
            }


    def _analyze_clauses_batch(
        self, clauses: List[Dict[str, Any]], rag_context: Dict[str, Any], batch_size: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Батч-анализ нескольких пунктов договора за один LLM вызов
        Экономит токены на system prompt

        Args:
            clauses: Список пунктов для анализа
            rag_context: Контекст из RAG
            batch_size: Сколько пунктов анализировать за раз (оптимально 10-15 для gpt-4o-mini)

        Returns:
            Список результатов анализа
        """
        all_analyses = []

        # Извлекаем контекст договора из RAG
        contract_summary = rag_context.get('contract_summary', {})
        contract_type = contract_summary.get('type', 'неизвестный')
        parties = contract_summary.get('parties', [])
        subject = contract_summary.get('subject', 'не указан')

        # Разбиваем на батчи
        for i in range(0, len(clauses), batch_size):
            batch = clauses[i:i + batch_size]

            logger.info(f"Analyzing batch {i//batch_size + 1}: clauses {i+1}-{i+len(batch)}")

            # Формируем промпт для батча
            clauses_text = ""
            for idx, clause in enumerate(batch, 1):
                clauses_text += f"""
[ПУНКТ {clause['number']}]
Заголовок: {clause['title']}
Текст: {clause['text'][:300]}{'...' if len(clause['text']) > 300 else ''}
---
"""

            # Определяем правовую базу по типу договора
            legal_framework = self._get_legal_framework(contract_type)

            prompt = f"""Ты - опытный юрист-эксперт по договорному праву РФ.

КОНТЕКСТ ДОГОВОРА:
- Тип договора: {contract_type}
- Стороны: {', '.join([p.get('name', '') for p in parties]) if parties else 'не указаны'}
- Предмет: {subject}

ПРАВОВАЯ БАЗА ДЛЯ ДАННОГО ТИПА:
{legal_framework}

ЗАДАЧА: Проанализируй {len(batch)} пунктов договора как профессиональный юрист.

<user_document>
{clauses_text}
</user_document>

Для КАЖДОГО пункта проведи детальную юридическую экспертизу и верни JSON в массиве:
[
  {{
    "clause_number": <номер пункта>,
    "clarity_score": <0-10, где 10 - идеально чёткая формулировка>,
    "legal_compliance": {{
      "score": <0-10, где 10 - полное соответствие ГК РФ>,
      "issues": ["конкретная проблема со ссылкой на статью ГК РФ"],
      "relevant_laws": ["ст. 421 ГК РФ - свобода договора"]
    }},
    "risks": [
      {{
        "risk_type": "legal|financial|operational|reputational",
        "severity": "high|medium|low",
        "probability": "high|medium|low",
        "title": "Краткое название риска",
        "description": "Подробное описание риска и его последствий",
        "consequences": "Конкретные последствия для вашей компании"
      }}
    ],
    "recommendations": [
      {{
        "priority": "critical|high|medium|low",
        "category": "legal_compliance|risk_mitigation|financial_optimization|clarity_improvement",
        "title": "Краткое название рекомендации",
        "description": "Конкретная рекомендация с обоснованием",
        "reasoning": "Почему это важно",
        "expected_benefit": "Ожидаемая польза от внедрения"
      }}
    ],
    "ambiguities": ["Конкретная двусмысленность в формулировке"],
    "missing_elements": ["Отсутствующий элемент, обязательный по ГК РФ"]
  }}
]

ТРЕБОВАНИЯ К АНАЛИЗУ:
1. **ВАЖНО:** Не ставь оценки 0/10 или 1/10 без КРАЙНЕ веской причины. Минимальная оценка для обычного текста - 3/10. Оценка 0/10 допустима ТОЛЬКО если:
   - Текст полностью отсутствует или нечитаем
   - Пункт содержит прямое нарушение закона
   - Формулировка абсолютно непригодна для использования
2. Оценивай реальный текст по существу, а не формально
3. В legal_compliance указывай конкретные статьи ГК РФ (ст. 309, 310, 330, 421, 431, 450, 451, 702, 708 и др.)
4. В risks описывай РЕАЛЬНЫЕ юридические риски с конкретными последствиями
5. В recommendations давай КОНКРЕТНЫЕ применимые советы, не общие фразы
6. Если пункт действительно проблемный - укажи это с детальным обоснованием"""

            try:
                # Используем быструю модель для первого уровня
                logger.info(f"🔍 DEBUG: Using model = {self.llm.model}, provider = {self.llm.provider}")
                logger.info(f"🔍 DEBUG: Prompt length = {len(prompt)} characters (batch of {len(batch)} clauses)")
                response = self.llm.call(
                    prompt=prompt,
                    system_prompt="""Ты - ведущий эксперт по договорному праву РФ с 15-летним опытом.

ТВОЯ РОЛЬ: Анализируй договоры как профессиональный юрист, выявляя РЕАЛЬНЫЕ риски и давая КОНКРЕТНЫЕ рекомендации.

КРИТИЧЕСКИ ВАЖНО:
1. Отвечай СТРОГО в формате JSON массива
2. Проводи РЕАЛЬНУЮ юридическую экспертизу, не формальную
3. Ссылайся на конкретные статьи ГК РФ (ст. 309, 310, 330, 421, 431, 450, 451 и др.)
4. Оценки давай по реальному качеству формулировок, не ставь 0/10 без причины
5. Риски описывай с последствиями и вероятностью
6. Рекомендации должны быть КОНКРЕТНЫМИ и ПРИМЕНИМЫМИ

Твой анализ будет использован юристами компании для принятия решений!""",
                    response_format="json",
                    temperature=0.2,
                    max_tokens=settings.llm_test_max_tokens if settings.llm_test_mode else settings.llm_max_tokens
                )

                # Parse response
                batch_analyses = response if isinstance(response, list) else []

                # Валидация оценок: нормализуем к диапазону 1-10
                for analysis in batch_analyses:
                    clarity = analysis.get('clarity_score', 0)
                    if not isinstance(clarity, (int, float)) or clarity < 1:
                        logger.warning(f"Clause {analysis.get('clause_number')} has clarity_score={clarity}, clamping to 1")
                        analysis['clarity_score'] = 1
                    elif clarity > 10:
                        analysis['clarity_score'] = 10

                    if isinstance(analysis.get('legal_compliance'), dict):
                        score = analysis['legal_compliance'].get('score', 0)
                        if not isinstance(score, (int, float)) or score < 1:
                            logger.warning(f"Clause {analysis.get('clause_number')} has legal_compliance={score}, clamping to 1")
                            analysis['legal_compliance']['score'] = 1
                            if not analysis['legal_compliance'].get('issues'):
                                analysis['legal_compliance']['issues'] = ['Требуется дополнительная правовая экспертиза']
                        elif score > 10:
                            analysis['legal_compliance']['score'] = 10

                if not batch_analyses:
                    logger.warning(f"Batch analysis returned empty/invalid response, falling back to individual analysis")
                    # Fallback: analyze individually
                    for clause in batch:
                        try:
                            analysis = self._analyze_clause_detailed(clause, rag_context)
                            all_analyses.append(analysis)
                        except Exception as e:
                            logger.error(f"Individual analysis failed for clause {clause['number']}: {e}")
                            all_analyses.append(self._get_fallback_analysis(clause))
                else:
                    # Add xpath from original clauses
                    for analysis in batch_analyses:
                        clause_num = analysis.get('clause_number')
                        # Find matching clause
                        for clause in batch:
                            if clause['number'] == clause_num:
                                analysis['clause_xpath'] = clause['xpath']
                                analysis['clause_title'] = clause['title']
                                break
                        all_analyses.append(analysis)

                logger.info(f"✓ Batch {i//batch_size + 1} analyzed: {len(batch_analyses)} clauses")

            except Exception as e:
                logger.error(f"Batch analysis failed: {e}, falling back to individual analysis")
                # Fallback: analyze individually
                for clause in batch:
                    try:
                        analysis = self._analyze_clause_detailed(clause, rag_context)
                        all_analyses.append(analysis)
                    except Exception as e2:
                        logger.error(f"Individual analysis failed for clause {clause['number']}: {e2}")
                        all_analyses.append(self._get_fallback_analysis(clause))

        return all_analyses

    def analyze_deep(self, clause_ids: list, contract_id: str, xml_content: str, rag_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Глубокий анализ конкретных пунктов с использованием gpt-4o (Уровень 2)
        
        Args:
            clause_ids: Список ID пунктов для глубокого анализа
            contract_id: ID договора
            xml_content: XML контент договора
            rag_context: Контекст из RAG
            
        Returns:
            Список детальных анализов пунктов с прецедентами и рекомендациями
        """
        from config.settings import settings
        from ..services.llm_gateway import LLMGateway
        
        logger.info(f"Starting DEEP analysis (Level 2) for {len(clause_ids)} clauses with {settings.llm_deep_model}")
        
        # Create deep LLM with gpt-4o
        deep_llm = LLMGateway(model=settings.llm_deep_model)
        
        # Extract clauses
        all_clauses = self._extract_contract_clauses(xml_content)
        selected_clauses = [c for c in all_clauses if c['id'] in clause_ids or c['number'] in clause_ids]
        
        if not selected_clauses:
            logger.warning(f"No clauses found for deep analysis with ids: {clause_ids}")
            return []
        
        deep_analyses = []
        
        for clause in selected_clauses:
            logger.info(f"Deep analyzing clause {clause['number']}: {clause['title'][:60]}")
            
            # Detailed prompt for deep analysis
            prompt = f"""Выполни ГЛУБОКИЙ юридический анализ пункта договора.

ПУНКТ №{clause['number']}: {clause['title']}
ТЕКСТ:
{clause['text']}

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{rag_context.get('context', '')[:1000]}

Проведи детальную экспертизу:

1. ЮРИДИЧЕСКИЙ АНАЛИЗ:
   - Соответствие ГК РФ, специальным законам
   - Ссылки на конкретные статьи законов
   - Выявление юридических коллизий
   - Анализ исполнимости через суд

2. РИСКИ:
   - Типичные категории споров по аналогичным пунктам
   - Финансовые последствия (диапазоны сумм)
   - Вероятность возникновения спора (%)
   ВАЖНО: НЕ выдумывай конкретные номера судебных дел и даты! Указывай только общие тенденции судебной практики.

3. АЛЬТЕРНАТИВНЫЕ ФОРМУЛИРОВКИ:
   - 2-3 варианта улучшенных формулировок
   - Обоснование каждого варианта

4. РЕКОМЕНДАЦИИ:
   - Общие позиции ВС РФ по аналогичным вопросам
   - Отраслевые стандарты

Верни JSON:
{{
  "clause_number": {clause['number']},
  "deep_legal_analysis": {{
    "compliance_score": 0-10,
    "relevant_laws": [
      {{
        "law": "ГК РФ",
        "article": "ст. 421",
        "relevance": "объяснение применимости",
        "compliance_status": "compliant|non_compliant|unclear"
      }}
    ],
    "legal_conflicts": ["конфликт 1", "конфликт 2"],
    "enforceability_score": 0-10,
    "enforceability_notes": "анализ исполнимости"
  }},
  "risks": [
    {{
      "risk_type": "тип",
      "severity": "critical|high|medium|low",
      "probability_percent": 0-100,
      "description": "детальное описание",
      "financial_impact_range": "от X до Y рублей",
      "typical_court_practice": "общая тенденция судебной практики",
      "mitigation": "как минимизировать"
    }}
  ],
  "alternative_formulations": [
    {{
      "variant_number": 1,
      "formulation": "текст формулировки",
      "advantages": ["преимущество 1", "преимущество 2"],
      "legal_basis": "обоснование"
    }}
  ],
  "recommendations": [
    {{
      "source": "ВС РФ / отраслевой стандарт",
      "recommendation": "рекомендация"
    }}
  ],
  "overall_risk_score": 0-100,
  "priority": "critical|high|medium|low",
  "summary": "краткое резюме глубокого анализа"
}}"""

            try:
                response = deep_llm.call(
                    prompt=prompt,
                    system_prompt="Ты ведущий эксперт по договорному праву РФ. Проводишь детальную экспертизу на уровне старшего партнёра юридической фирмы. Используешь конкретные ссылки на законы, судебную практику и прецеденты.",
                    response_format="json",
                    temperature=0.3,
                    max_tokens=settings.llm_max_tokens,
                    use_cache=True,
                    db_session=self.db
                )
                
                response['clause_id'] = clause['id']
                response['clause_xpath'] = clause['xpath']
                response['clause_title'] = clause['title']
                response['analysis_level'] = 'deep'
                response['model_used'] = settings.llm_deep_model
                
                deep_analyses.append(response)
                logger.info(f"✓ Deep analysis complete for clause {clause['number']}: {response.get('overall_risk_score', 'N/A')}/100 risk score")
                
            except Exception as e:
                logger.error(f"Deep analysis failed for clause {clause['number']}: {e}")
                # Fallback
                deep_analyses.append({
                    'clause_number': clause['number'],
                    'clause_id': clause['id'],
                    'error': str(e),
                    'analysis_level': 'deep',
                    'summary': 'Глубокий анализ не удался из-за ошибки'
                })
        
        logger.info(f"Deep analysis complete: {len(deep_analyses)} clauses analyzed with {settings.llm_deep_model}")
        return deep_analyses

    def _analyze_clause_detailed(
        self, clause: Dict[str, Any], rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Детальный LLM-анализ отдельного пункта договора
        Returns detailed analysis including risks, issues, recommendations
        """
        try:
            # Сокращённый промпт для избежания переполнения
            prompt = f"""Проанализируй пункт договора:

ПУНКТ №{clause['number']}: {clause['title']}
ТЕКСТ: {clause['text']}

Оцени:
1. Чёткость формулировки (0-10)
2. Правовое соответствие (0-10)
3. Риски (тип, серьёзность, описание)
4. Рекомендации по улучшению
5. Двусмысленности
6. Отсутствующие элементы

JSON формат:
{{
  "clause_id": "{clause['id']}",
  "clarity_score": 0-10,
  "clarity_assessment": "подробная оценка чёткости формулировки",
  "legal_compliance": {{
    "score": 0-10,
    "issues": ["проблема 1", "проблема 2"],
    "relevant_laws": ["ГК РФ ст. XXX", "закон Y"]
  }},
  "risks": [
    {{
      "risk_type": "financial|legal|operational|reputational",
      "severity": "critical|high|medium|low",
      "probability": "high|medium|low",
      "title": "краткое название риска",
      "description": "ПОДРОБНОЕ описание риска",
      "consequences": "возможные последствия",
      "affected_party": "кто пострадает"
    }}
  ],
  "ambiguities": ["двусмысленность 1", "двусмысленность 2"],
  "missing_elements": ["что отсутствует в пункте"],
  "recommendations": [
    {{
      "priority": "critical|high|medium|low",
      "recommendation": "что сделать",
      "reasoning": "почему это важно",
      "suggested_text": "предлагаемая формулировка (если применимо)"
    }}
  ],
  "precedents": ["судебная практика"],
  "overall_assessment": "общая оценка",
  "improvement_priority": "critical|high|medium|low"
}}"""

            logger.info(f"Analyzing clause {clause['number']}: {clause['title'][:50]}")

            # Try with JSON format first
            try:
                response = self.llm.call(
                    prompt=prompt,
                    system_prompt=self.get_system_prompt(),
                    response_format="json",
                    temperature=0.2
                )

                # Parse JSON response (already parsed if response_format='json')
                analysis = response if isinstance(response, dict) else json.loads(response)

            except (json.JSONDecodeError, ValueError) as e:
                # Fallback: try with text format and parse manually
                logger.warning(f"JSON format failed for clause {clause['number']}, trying text format: {e}")

                try:
                    response = self.llm.call(
                        prompt=prompt + "\n\nВерни ТОЛЬКО JSON, без дополнительного текста.",
                        system_prompt=self.get_system_prompt(),
                        response_format="text",
                        temperature=0.2
                    )

                    # Try to extract JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        analysis = json.loads(json_match.group(0))
                    else:
                        logger.error(f"No JSON found in text response for clause {clause['number']}")
                        return self._get_fallback_analysis(clause)

                except Exception as e2:
                    logger.error(f"Text format also failed for clause {clause['number']}: {e2}")
                    return self._get_fallback_analysis(clause)

            analysis['clause_number'] = clause['number']
            analysis['clause_xpath'] = clause['xpath']

            logger.info(f"✓ Clause {clause['number']} analyzed: {len(analysis.get('risks', []))} risks, {len(analysis.get('recommendations', []))} recommendations")

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for clause {clause['number']}: {e}")
            return self._get_fallback_analysis(clause)
        except Exception as e:
            logger.error(f"Clause analysis failed for {clause['number']}: {e}")
            return self._get_fallback_analysis(clause)

    def _get_fallback_analysis(self, clause: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis if LLM fails"""
        return {
            'clause_id': clause['id'],
            'clause_number': clause['number'],
            'clause_xpath': clause['xpath'],
            'clarity_score': 5,
            'clarity_assessment': 'Анализ не выполнен из-за ошибки',
            'legal_compliance': {'score': 5, 'issues': [], 'relevant_laws': []},
            'risks': [],
            'ambiguities': [],
            'missing_elements': [],
            'recommendations': [],
            'precedents': [],
            'overall_assessment': 'Требуется повторный анализ',
            'improvement_priority': 'medium'
        }

    def _identify_risks(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]],
        company_conditions: Optional[List[Dict[str, Any]]] = None,
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> List[ContractRisk]:
        """
        Two-pass risk analysis:
        Pass 1 - full-text review for systemic risks and cross-section issues.
        Pass 2 - clause-level review for concrete, localized risks.
        """
        from config.settings import settings

        all_risks: List[ContractRisk] = []
        self._full_text_analysis = None
        is_local_provider = self.risk_analyzer._is_local_provider()
        use_full_text = getattr(settings, 'full_text_analysis', True)

        if is_local_provider and not getattr(settings, 'llm_local_full_text_analysis', False):
            use_full_text = False
            progress_updater = getattr(self, '_progress_updater', None)
            if callable(progress_updater):
                progress_updater(40, "Локальная LLM: анализируем по разделам без полного прохода...")
            logger.info("Skipping full-text analysis for local LLM provider")

        if use_full_text:
            try:
                plain_text = self._extract_plain_text(xml_content)
                logger.info(f"Pass 1: Full-text analysis - {len(plain_text)} chars (~{len(plain_text)//4} tokens)")

                full_text_result = self.risk_analyzer.analyze_full_text(
                    plain_text=plain_text,
                    rag_context=rag_context,
                    company_conditions=company_conditions,
                    analysis_context=analysis_context,
                )
                self._full_text_analysis = full_text_result
                self._merge_required_fields_from_analyses([{
                    'clause_id': 'full_text_analysis',
                    'clause_title': 'Полнотекстовый анализ',
                    'clause_xpath': '',
                    'required_fields': full_text_result.get('required_fields', []),
                }])

                type_mapping = {
                    'compliance': 'legal',
                    'regulatory': 'legal',
                    'contractual': 'legal',
                    'process': 'operational',
                    'business': 'operational',
                }
                severity_mapping = {
                    'significant': 'high',
                    'minor': 'low',
                    'warning': 'medium',
                }
                allowed_types = {'financial', 'legal', 'operational', 'reputational', 'general'}
                allowed_severities = {'critical', 'high', 'medium', 'low', 'info'}
                allowed_probabilities = {'high', 'medium', 'low'}

                for risk_data in full_text_result.get('risks', []):
                    try:
                        raw_type = (risk_data.get('type', risk_data.get('risk_type', 'legal')) or 'legal').lower()
                        raw_severity = (risk_data.get('severity', 'medium') or 'medium').lower()
                        raw_probability = (risk_data.get('probability', 'medium') or 'medium').lower()

                        normalized_type = type_mapping.get(raw_type, raw_type)
                        if normalized_type not in allowed_types:
                            normalized_type = 'legal'
                        normalized_severity = severity_mapping.get(raw_severity, raw_severity)
                        if normalized_severity not in allowed_severities:
                            normalized_severity = 'medium'

                        risk = ContractRisk(
                            risk_type=normalized_type,
                            severity=normalized_severity,
                            probability=raw_probability if raw_probability in allowed_probabilities else 'medium',
                            title=risk_data.get('title', 'Риск')[:255],
                            description=risk_data.get('description', ''),
                            consequences=risk_data.get('consequences', ''),
                            xpath_location='',
                            section_name='full_text_analysis',
                        )
                        all_risks.append(risk)
                    except Exception as exc:
                        logger.error(f"Failed to create full-text risk: {exc}")

                logger.info(f"Pass 1 complete: {len(all_risks)} risks from full-text analysis")
            except Exception as exc:
                logger.error(f"Full-text analysis failed, continuing with clause-level: {exc}")

        try:
            logger.info("Pass 2: Clause-level analysis...")
            clauses = self.clause_extractor.extract_clauses(xml_content)
            logger.info(f"Extracted {len(clauses)} clauses for analysis")

            if not clauses:
                logger.warning("No clauses extracted, falling back to legacy method")
                if not all_risks:
                    return self._identify_risks_legacy(
                        xml_content, structure, rag_context, counterparty_data, analysis_context
                    )
                return all_risks

            max_clauses = settings.llm_test_max_clauses if settings.llm_test_mode else len(clauses)
            batch_size = settings.llm_batch_size
            logger.info(f"Will analyze {min(len(clauses), max_clauses)} clauses (smart batching)")

            def _on_batch_progress(completed_batches: int, total_batches: int) -> None:
                progress_updater = getattr(self, '_progress_updater', None)
                if not callable(progress_updater) or total_batches <= 0:
                    return
                start_pct = 42
                end_pct = 58
                pct = start_pct + int(((end_pct - start_pct) * completed_batches) / total_batches)
                progress_updater(
                    min(end_pct, pct),
                    f"AI анализ: обработка разделов {completed_batches}/{total_batches}..."
                )

            all_clause_analyses = self.risk_analyzer.analyze_clauses_batch(
                clauses[:max_clauses],
                rag_context,
                batch_size=batch_size,
                company_conditions=company_conditions,
                analysis_context=analysis_context,
                progress_callback=_on_batch_progress,
            )
            logger.info(f"Batch analysis returned {len(all_clause_analyses)} results")

            clause_risks = self.risk_analyzer.identify_risks(all_clause_analyses)
            all_risks.extend(clause_risks)

            # Дедупликация: убираем дубли между Pass 1 и Pass 2
            all_risks = self._deduplicate_risks(all_risks)

            if all_clause_analyses:
                self._merge_required_fields_from_analyses(all_clause_analyses)
                self._store_clause_analyses(all_clause_analyses)
                logger.info(
                    f"Pass 2 complete: {len(clause_risks)} clause-level risks from {len(all_clause_analyses)} clauses"
                )
            else:
                logger.warning("No clauses were successfully analyzed, using legacy method")
                if not all_risks:
                    return self._identify_risks_legacy(
                        xml_content, structure, rag_context, counterparty_data, analysis_context
                    )

            logger.info(f"Total risks (both passes): {len(all_risks)}")
            return all_risks

        except Exception as exc:
            logger.error(f"Detailed risk identification failed: {exc}")
            import traceback
            traceback.print_exc()
            if is_local_provider:
                raise
            if not all_risks:
                return self._identify_risks_legacy(
                    xml_content, structure, rag_context, counterparty_data, analysis_context
                )
            return all_risks

    def _deduplicate_risks(self, risks: List) -> List:
        """Remove duplicate risks based on title similarity"""
        if len(risks) <= 1:
            return risks

        unique = []
        seen_titles = []

        # Priority order for severity
        severity_priority = {'critical': 0, 'high': 1, 'significant': 2, 'medium': 3, 'minor': 4, 'low': 5}

        for risk in risks:
            title_lower = (risk.title or '').lower().strip()
            is_duplicate = False

            for i, seen in enumerate(seen_titles):
                # Check for exact or near-exact title match
                if title_lower == seen:
                    is_duplicate = True
                    # Keep the one with higher severity
                    existing = unique[i]
                    if severity_priority.get(risk.severity, 3) < severity_priority.get(existing.severity, 3):
                        unique[i] = risk
                        seen_titles[i] = title_lower
                    break

                # Check for high overlap (one title contains the other)
                if len(title_lower) > 10 and len(seen) > 10:
                    if title_lower in seen or seen in title_lower:
                        is_duplicate = True
                        existing = unique[i]
                        if severity_priority.get(risk.severity, 3) < severity_priority.get(existing.severity, 3):
                            unique[i] = risk
                            seen_titles[i] = title_lower
                        break

            if not is_duplicate:
                unique.append(risk)
                seen_titles.append(title_lower)

        removed = len(risks) - len(unique)
        if removed:
            logger.info(f"Deduplication: removed {removed} duplicate risks ({len(risks)} → {len(unique)})")
        return unique

    def _store_clause_analyses(self, analyses: List[Dict[str, Any]]):
        """Store detailed clause analyses for UI display"""
        # Сохраняем в памяти для передачи в результат
        if not hasattr(self, '_clause_analyses'):
            self._clause_analyses = []
        self._clause_analyses = analyses

    def _extract_required_fields(self, xml_content: str) -> List[Dict[str, Any]]:
        """Extract explicit placeholders and blanks that must be filled by the user."""
        clauses = self.clause_extractor.extract_clauses(xml_content)
        required_fields: List[Dict[str, Any]] = []
        placeholder_clause_ids: set[str] = set()
        patterns = [
            re.compile(r"_{2,}"),
            re.compile(r"\[(?:[^\]]*(?:указать|заполнить|вписать|определить)[^\]]*)\]", re.IGNORECASE),
        ]

        for clause in clauses:
            clause_text = clause.get('text', '')
            matches = []
            for pattern in patterns:
                matches.extend(list(pattern.finditer(clause_text)))
            if not matches:
                continue

            placeholder_clause_ids.add(clause.get('id', ''))
            for match in matches:
                start = max(0, match.start() - 60)
                end = min(len(clause_text), match.end() + 60)
                snippet = clause_text[start:end].strip()
                required_fields.append({
                    'title': clause.get('title') or 'Нужно заполнить поле',
                    'description': 'В договоре есть незаполненное место, которое нужно заполнить до использования документа.',
                    'snippet': snippet,
                    'section_name': clause.get('title') or clause.get('id', ''),
                    'xpath_location': clause.get('xpath', ''),
                    'needs_user_input': True,
                    'autofill_blocked': True,
                })

        self._required_fields = self._dedupe_required_fields(required_fields)
        self._placeholder_clause_ids = placeholder_clause_ids
        return self._required_fields

    def _merge_required_fields_from_analyses(self, analyses: List[Dict[str, Any]]) -> None:
        """Merge LLM-detected placeholders with regex-detected placeholders."""
        existing = list(getattr(self, '_required_fields', []))
        for analysis in analyses:
            for item in analysis.get('required_fields', []):
                existing.append({
                    'title': item.get('title') or 'Нужно заполнить поле',
                    'description': item.get('description') or 'В договоре есть незаполненное место.',
                    'snippet': item.get('snippet') or '',
                    'section_name': analysis.get('clause_title') or analysis.get('clause_id', ''),
                    'xpath_location': analysis.get('clause_xpath', ''),
                    'needs_user_input': item.get('needs_user_input', True),
                    'user_question': item.get('user_question') or '',
                    'missing_data_points': item.get('missing_data_points') or [],
                    'autofill_blocked': item.get('autofill_blocked', item.get('needs_user_input', True)),
                })
        self._required_fields = self._dedupe_required_fields(existing)

    def _dedupe_required_fields(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for item in items:
            item = self._enrich_required_field(item)
            if self._should_ignore_required_field(item):
                continue
            key = '|'.join([
                item.get('section_name', ''),
                item.get('xpath_location', ''),
                item.get('snippet', ''),
            ]).strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    @staticmethod
    def _enrich_required_field(item: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(item)
        title = (enriched.get('title') or '').strip()
        snippet = (enriched.get('snippet') or '').strip()
        description = (enriched.get('description') or '').strip()
        combined = ' '.join([title, snippet, description]).lower()

        enriched.setdefault('needs_user_input', True)
        enriched.setdefault('autofill_blocked', bool(enriched.get('needs_user_input', True)))

        if not enriched.get('missing_data_points'):
            missing_data_points: List[str] = []
            if any(marker in combined for marker in ('предмет', 'товар', 'услуг', 'работ', 'объект', 'спецификац')):
                missing_data_points = ['точное описание предмета', 'объем/количество', 'ключевые характеристики или спецификация']
            elif any(marker in combined for marker in ('оплат', 'цен', 'стоим', 'сумм', 'тариф')):
                missing_data_points = ['сумма или цена', 'срок оплаты', 'порядок оплаты']
            elif any(marker in combined for marker in ('срок', 'дата', 'период', 'календар')):
                missing_data_points = ['конкретная дата или срок', 'событие-триггер начала/окончания']
            elif any(marker in combined for marker in ('банк', 'бик', 'к/с', 'р/с', 'счёт', 'счет', 'инн', 'кпп')):
                missing_data_points = ['полные реквизиты', 'банковские данные']
            enriched['missing_data_points'] = missing_data_points

        if not enriched.get('user_question'):
            if any(marker in combined for marker in ('предмет', 'товар', 'услуг', 'работ', 'объект', 'спецификац')):
                enriched['user_question'] = (
                    'Уточните предмет договора: что именно передается, выполняется или оказывается, '
                    'в каком объеме и с какими характеристиками?'
                )
            elif any(marker in combined for marker in ('оплат', 'цен', 'стоим', 'сумм', 'тариф')):
                enriched['user_question'] = (
                    'Какие точные денежные условия нужно подставить: сумма, цена, валюта, срок и порядок оплаты?'
                )
            elif any(marker in combined for marker in ('срок', 'дата', 'период', 'календар')):
                enriched['user_question'] = (
                    'Какую точную дату, срок или событие-триггер нужно указать в этом пункте?'
                )
            else:
                enriched['user_question'] = (
                    'Какие именно данные нужно получить от пользователя, чтобы корректно заполнить этот пункт без выдумывания условий?'
                )

        if any(marker in combined for marker in ('предмет', 'товар', 'услуг', 'работ', 'объект', 'спецификац')):
            enriched['description'] = (
                'Система не должна придумывать предмет договора или его параметры. '
                'Нужно запросить у пользователя конкретные данные и только после этого заполнять документ.'
            )
        elif not description:
            enriched['description'] = 'В договоре есть незаполненное место. Для корректного заполнения нужны данные от пользователя.'

        return enriched

    @staticmethod
    def _should_ignore_required_field(item: Dict[str, Any]) -> bool:
        return should_ignore_required_field(item)

    def _filter_placeholder_risks(self, risks: List[ContractRisk]) -> List[ContractRisk]:
        """Remove pseudo-risks caused by placeholders/metadata and deduplicate obvious repeats."""
        placeholder_clause_ids = getattr(self, '_placeholder_clause_ids', set())
        analysis_context = getattr(self, '_analysis_context', {}) or {}
        analysis_date_iso = analysis_context.get('analysis_date')
        technical_markers = [
            'uuid', 'метадан', 'metadata', 'parsed_at', 'file_name', 'дата создания',
            'author', 'автор', 'title', 'без названия', 'docx',
        ]
        filtered: List[ContractRisk] = []
        for risk in risks:
            combined = ' '.join([risk.title or '', risk.description or '']).lower()
            is_placeholder_clause = (risk.section_name or '') in placeholder_clause_ids
            mentions_placeholder = any(marker in combined for marker in [
                'незаполн', 'пропуск', 'пустое поле', '___', 'placeholder', 'не заполн',
            ])
            mentions_technical_metadata = any(marker in combined for marker in technical_markers)
            if is_placeholder_clause and mentions_placeholder:
                continue
            if mentions_technical_metadata:
                continue
            if should_ignore_future_date_risk(' '.join([risk.title or '', risk.description or '', risk.consequences or '']), analysis_date_iso):
                continue
            if should_ignore_signatory_authority_risk(' '.join([risk.title or '', risk.description or '', risk.consequences or ''])):
                continue
            filtered.append(risk)
        return self._dedupe_risks(filtered)

    @staticmethod
    def _dedupe_risks(risks: List[ContractRisk]) -> List[ContractRisk]:
        """Collapse obviously duplicated risks while preserving the strongest variant."""
        severity_rank = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        probability_rank = {'low': 1, 'medium': 2, 'high': 3}
        deduped: dict[str, ContractRisk] = {}

        for risk in risks:
            normalized_title = re.sub(r'\s+', ' ', re.sub(r'[^a-zа-я0-9]+', ' ', (risk.title or '').lower())).strip()
            fallback_title = re.sub(
                r'\s+',
                ' ',
                re.sub(r'[^a-zа-я0-9]+', ' ', (risk.description or '').lower())[:120],
            ).strip()
            key = '|'.join([
                risk.risk_type or 'general',
                normalized_title or fallback_title,
            ]).strip('|')

            if not key:
                key = f"risk-{id(risk)}"

            existing = deduped.get(key)
            if existing is None:
                deduped[key] = risk
                continue

            existing_score = (
                severity_rank.get(existing.severity or 'info', 0),
                probability_rank.get(existing.probability or 'low', 1),
                len(existing.description or ''),
            )
            current_score = (
                severity_rank.get(risk.severity or 'info', 0),
                probability_rank.get(risk.probability or 'low', 1),
                len(risk.description or ''),
            )
            if current_score > existing_score:
                deduped[key] = risk

        return list(deduped.values())

    def _identify_risks_legacy(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]],
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> List[ContractRisk]:
        logger.info("⚠️ DEBUG: _identify_risks_legacy called (OLD method, NO batching, EXPENSIVE!)")
        """Legacy risk identification method (fallback)"""
        try:
            # Prepare prompt
            prompt = self._build_risk_identification_prompt(
                xml_content, structure, rag_context, counterparty_data, analysis_context
            )

            # Call LLM
            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                response_format="json",
                temperature=0.3
            )

            # Parse JSON response
            risks_data = response if isinstance(response, dict) else json.loads(response)

            # Convert to ContractRisk objects
            risks = []
            for risk_dict in risks_data.get('risks', []):
                risk = ContractRisk(
                    risk_type=risk_dict.get('risk_type', 'legal'),
                    severity=risk_dict.get('severity', 'medium'),
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
            logger.error(f"Legacy risk identification failed: {e}")
            return []

    def _build_risk_identification_prompt(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]],
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for risk identification"""
        prompt = "Проанализируй договор и выяви только реальные существенные риски.\n\n"
        prompt += "<user_document>\n"
        prompt += xml_content[:5000]
        prompt += "\n</user_document>\n\n"

        prompt += "СТРУКТУРА ДОГОВОРА:\n"
        prompt += json.dumps(structure, ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "РЕЛЕВАНТНЫЙ ПРАВОВОЙ КОНТЕКСТ (из RAG):\n"
            prompt += rag_context['context'][:3000]
            prompt += "\n\n"

        if counterparty_data:
            prompt += "РЕЗУЛЬТАТЫ ПРОВЕРКИ КОНТРАГЕНТА:\n"
            prompt += json.dumps(counterparty_data, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        if analysis_context:
            prompt += "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА АНАЛИЗА:\n"
            if analysis_context.get('analysis_date'):
                prompt += (
                    f"- Текущая дата анализа: {analysis_context['analysis_date']}. "
                    "Оценивай все даты относительно этой даты.\n"
                )
            if analysis_context.get('analysis_perspective'):
                prompt += (
                    f"- Анализируй договор в интересах стороны: {analysis_context['analysis_perspective']}.\n"
                )
            prompt += (
                "- Не считай рисками служебные метаданные файла и парсинга.\n"
                "- Незаполненные поля, пропуски и шаблонные плейсхолдеры не являются рисками сами по себе.\n"
                "- Проект договора готовится к подписанию: отсутствие живых подписей, печатей и М.П. в черновике не является риском.\n"
                "- Не требуй выписку ЕГРЮЛ, доверенность или иные внешние подтверждения полномочий подписанта, если в тексте нет прямого противоречия полномочиям.\n"
                "- Не называй дату будущей, если она не позже текущей даты анализа.\n\n"
            )

        prompt += """Выделяй риски только по категориям:
- financial
- legal
- operational
- reputational

Верни JSON:
{
  "risks": [
    {
      "risk_type": "financial|legal|operational|reputational|general",
      "severity": "critical|high|medium|low|info",
      "probability": "high|medium|low",
      "title": "Краткое название риска",
      "description": "Подробное описание риска",
      "consequences": "Качественные последствия",
      "xpath_location": "XPath к проблемному месту",
      "section_name": "Раздел",
      "rag_sources": ["Источник 1", "Источник 2"]
    }
  ]
}

Верни ТОЛЬКО валидный JSON, без дополнительного текста."""

        return prompt

    def _save_risks(self, analysis_id: str, contract_id: str, risks: List[ContractRisk]):
        """Save risks to database"""
        allowed_types = {'financial', 'legal', 'operational', 'reputational', 'general'}
        type_mapping = {
            'compliance': 'legal',
            'regulatory': 'legal',
            'contractual': 'legal',
            'process': 'operational',
            'business': 'operational',
        }
        allowed_severities = {'critical', 'high', 'medium', 'low', 'info'}
        severity_mapping = {
            'significant': 'high',
            'minor': 'low',
            'warning': 'medium',
        }
        allowed_probabilities = {'high', 'medium', 'low'}

        for risk in risks:
            raw_type = (risk.risk_type or 'legal').lower()
            normalized_type = type_mapping.get(raw_type, raw_type)
            if normalized_type not in allowed_types:
                normalized_type = 'legal'
            risk.risk_type = normalized_type

            raw_severity = (risk.severity or 'medium').lower()
            normalized_severity = severity_mapping.get(raw_severity, raw_severity)
            if normalized_severity not in allowed_severities:
                normalized_severity = 'medium'
            risk.severity = normalized_severity

            raw_probability = (risk.probability or 'medium').lower()
            risk.probability = raw_probability if raw_probability in allowed_probabilities else 'medium'
            risk.analysis_id = analysis_id
            risk.contract_id = contract_id
            self.db.add(risk)
        self.db.commit()

    @staticmethod
    def _normalize_complexity(value: str | None) -> str | None:
        """Normalize implementation_complexity to match DB constraint (easy/medium/hard)."""
        if not value:
            return None
        mapping = {'high': 'hard', 'low': 'easy', 'simple': 'easy', 'complex': 'hard', 'difficult': 'hard'}
        return mapping.get(value.lower(), value.lower()) if value.lower() in ('easy', 'medium', 'hard', *mapping) else 'medium'

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

    @staticmethod
    def _get_legal_framework(contract_type: str) -> str:
        """Return applicable legal framework based on contract type"""
        frameworks = {
            'employment': (
                "- Трудовой кодекс РФ (НЕ ГК РФ!) — главы 10-13 (заключение, изменение, прекращение ТД)\n"
                "- ст. 56-84.1 ТК РФ — основные нормы трудового договора\n"
                "- Закон о персональных данных (152-ФЗ)\n"
                "- ВАЖНО: ГК РФ к трудовым отношениям НЕ применяется"
            ),
            'supply': (
                "- ГК РФ, Глава 30 §3 (ст. 506-524) — Поставка товаров\n"
                "- ст. 309-310 ГК РФ — надлежащее исполнение обязательств\n"
                "- ст. 330-333 ГК РФ — неустойка\n"
                "- Закон о защите прав потребителей (если применимо)"
            ),
            'service': (
                "- ГК РФ, Глава 39 (ст. 779-783) — Возмездное оказание услуг\n"
                "- ст. 309-310 ГК РФ — надлежащее исполнение\n"
                "- ст. 421 ГК РФ — свобода договора"
            ),
            'lease': (
                "- ГК РФ, Глава 34 (ст. 606-670) — Аренда\n"
                "- ст. 609 ГК РФ — форма и госрегистрация\n"
                "- ст. 614 ГК РФ — арендная плата\n"
                "- ст. 619-620 ГК РФ — расторжение"
            ),
            'loan': (
                "- ГК РФ, Глава 42 (ст. 807-818) — Заём\n"
                "- Закон о потребительском кредите (353-ФЗ, если применимо)\n"
                "- ст. 809 ГК РФ — проценты\n"
                "- ст. 811 ГК РФ — последствия нарушения"
            ),
            'purchase': (
                "- ГК РФ, Глава 30 §1 (ст. 454-491) — Купля-продажа\n"
                "- ст. 469-477 ГК РФ — качество товара\n"
                "- ст. 475 ГК РФ — последствия передачи некачественного товара"
            ),
            'nda': (
                "- ст. 421 ГК РФ — свобода договора\n"
                "- ГК РФ, Часть 4, Глава 75 — Секрет производства (ноу-хау)\n"
                "- Закон о коммерческой тайне (98-ФЗ)\n"
                "- Закон о персональных данных (152-ФЗ, если применимо)"
            ),
            'license': (
                "- ГК РФ, Часть 4, Глава 69-70 (ст. 1225-1551) — Интеллектуальная собственность\n"
                "- ст. 1235-1238 ГК РФ — лицензионный договор\n"
                "- ст. 1286 ГК РФ — лицензионный договор об авторском праве"
            ),
            'construction': (
                "- ГК РФ, Глава 37 §3 (ст. 740-757) — Строительный подряд\n"
                "- Градостроительный кодекс РФ\n"
                "- ст. 743 ГК РФ — техническая документация и смета"
            ),
        }
        default_framework = (
            "- ГК РФ, общие положения об обязательствах (ст. 307-419)\n"
            "- ст. 421 ГК РФ — свобода договора\n"
            "- ст. 431 ГК РФ — толкование договора\n"
            "- ст. 432 ГК РФ — существенные условия"
        )
        return frameworks.get(contract_type, default_framework)

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
