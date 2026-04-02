# -*- coding: utf-8 -*-
"""
Recommendation Generator - Generate recommendations and suggested changes

Создает рекомендации и предложения по исправлению рисков в договорах
"""
from typing import Dict, Any, List, Optional
import json
from loguru import logger

from ..services.llm_gateway import LLMGateway
from ..models.analyzer_models import (
    ContractRisk,
    ContractRecommendation,
    ContractSuggestedChange,
    ContractAnnotation
)


class RecommendationGenerator:
    """
    Generates recommendations and suggested changes for contract risks

    Supports:
    - Risk-based recommendations with LLM
    - Automatic suggested text changes
    - Contract annotations for highlighting
    - Priority and complexity assessment
    """

    def __init__(self, llm_gateway: LLMGateway, system_prompt: str = ""):
        """
        Initialize recommendation generator

        Args:
            llm_gateway: LLM gateway for generation
            system_prompt: Optional system prompt for LLM calls
        """
        self.llm = llm_gateway
        self.system_prompt = system_prompt or "Ты — эксперт по юридическому анализу договоров. Все ответы давай ТОЛЬКО на русском языке."

    def generate_recommendations(
        self,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any],
        company_conditions: list = None,
        required_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ContractRecommendation]:
        """
        Generate recommendations based on identified risks

        Args:
            risks: List of identified contract risks
            rag_context: RAG context with legal references
            company_conditions: Optional list of user's company standard conditions

        Returns:
            List of ContractRecommendation objects
        """
        try:
            prompt = self._build_recommendations_prompt(
                risks,
                rag_context,
                company_conditions,
                required_fields,
            )

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_format="json",
                temperature=0.3
            )

            recommendations_data = response if isinstance(response, dict) else json.loads(response)

            recommendations = []
            for rec_dict in recommendations_data.get('recommendations', []):
                try:
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
                except Exception as e:
                    logger.error(f"Failed to create recommendation object: {e}")
                    continue

            if recommendations:
                logger.info(f"✓ Generated {len(recommendations)} recommendations")
                return recommendations

            logger.warning("LLM returned no recommendations, using deterministic fallback")
            return self.generate_fallback_recommendations(risks, required_fields)

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return self.generate_fallback_recommendations(risks, required_fields)

    def generate_fallback_recommendations(
        self,
        risks: List[ContractRisk],
        required_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ContractRecommendation]:
        """Build deterministic recommendations when LLM output is empty or invalid."""
        recommendations: List[ContractRecommendation] = []
        seen_keys: set[str] = set()
        severity_rank = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}

        for field in required_fields or []:
            title = (field.get('title') or 'Заполнить обязательное поле').strip()
            snippet = (field.get('snippet') or '').strip()
            key = f"field:{title.lower()}:{snippet.lower()[:120]}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            description = field.get('description') or 'В документе есть обязательное незаполненное место.'
            snippet_hint = f" Фрагмент: {snippet[:220]}" if snippet else ''
            user_question = (field.get('user_question') or '').strip()
            missing_points = field.get('missing_data_points') or []
            needs_user_input = field.get('needs_user_input', True)

            if needs_user_input:
                title_prefix = 'Запросить у пользователя данные'
                details = ''
                if missing_points:
                    details = ' Нужные данные: ' + ', '.join(str(point) for point in missing_points if point)
                question_hint = f" Вопрос пользователю: {user_question}" if user_question else ''
                recommendation_description = (
                    f"{description} Система не должна подставлять эти сведения автоматически."
                    f"{details}{question_hint}{snippet_hint}"
                )
                reasoning = (
                    'Без исходных бизнес-данных нельзя безопасно дописывать договор: это приведет к выдумыванию '
                    'существенных условий и искажению воли сторон.'
                )
                expected_benefit = (
                    'После получения данных от пользователя документ можно корректно заполнить без фантазирования условий.'
                )
            else:
                title_prefix = 'Заполнить'
                recommendation_description = (
                    f"{description} Заполните это место перед согласованием и подписанием документа."
                    f"{snippet_hint}"
                )
                reasoning = 'Проект договора должен содержать согласованные данные во всех обязательных полях.'
                expected_benefit = 'Документ станет пригоден для согласования, подписания и последующего исполнения.'

            recommendations.append(
                ContractRecommendation(
                    category='completion',
                    priority='high',
                    title=f"{title_prefix}: {title}",
                    description=recommendation_description,
                    reasoning=reasoning,
                    expected_benefit=expected_benefit,
                    implementation_complexity='easy',
                )
            )

        sorted_risks = sorted(
            risks,
            key=lambda risk: (
                severity_rank.get((risk.severity or 'info').lower(), 0),
                len(risk.description or ''),
            ),
            reverse=True,
        )

        for risk in sorted_risks:
            key = f"risk:{(risk.title or '').strip().lower()}:{(risk.section_name or '').strip().lower()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            priority = self._normalize_priority(getattr(risk, 'severity', None))
            recommendations.append(
                ContractRecommendation(
                    category=self._recommendation_category_from_risk(risk),
                    priority=priority,
                    title=self._build_fallback_title(risk),
                    description=self._build_fallback_description(risk),
                    reasoning=(
                        risk.description
                        or 'Рекомендация сформирована на основе автоматически выявленного риска.'
                    ),
                    expected_benefit=(
                        risk.consequences
                        or 'Снижение вероятности спора и более предсказуемое исполнение договора.'
                    ),
                    implementation_complexity=self._complexity_from_priority(priority),
                    related_risk_id=getattr(risk, 'id', None),
                )
            )

        logger.info(f"✓ Generated {len(recommendations)} fallback recommendations")
        return recommendations

    @staticmethod
    def _normalize_priority(value: Optional[str]) -> str:
        mapping = {
            'critical': 'critical',
            'high': 'high',
            'medium': 'medium',
            'low': 'low',
            'info': 'low',
        }
        return mapping.get((value or 'medium').lower(), 'medium')

    @staticmethod
    def _complexity_from_priority(priority: str) -> str:
        if priority == 'critical':
            return 'hard'
        if priority == 'high':
            return 'medium'
        return 'easy'

    @staticmethod
    def _recommendation_category_from_risk(risk: ContractRisk) -> str:
        risk_type = (risk.risk_type or 'general').lower()
        if risk_type == 'financial':
            return 'financial_optimization'
        if risk_type == 'legal':
            return 'legal_compliance'
        if risk_type == 'operational':
            return 'risk_mitigation'
        return 'general'

    def _build_fallback_title(self, risk: ContractRisk) -> str:
        combined = ' '.join([risk.title or '', risk.description or '']).lower()
        section = (risk.section_name or '').strip()

        if 'спецификац' in combined:
            return 'Подготовить и согласовать спецификации к договору'
        if 'оплат' in combined:
            return 'Зафиксировать сроки и порядок оплаты'
        if 'пролонгац' in combined:
            return 'Ограничить или уточнить автоматическую пролонгацию'
        if 'односторон' in combined and 'отказ' in combined:
            return 'Ограничить право на односторонний отказ от товара'
        if 'срок' in combined or 'дата' in combined:
            return 'Уточнить сроки и порядок исполнения'
        if section:
            return f'Переработать раздел: {section}'
        return f'Устранить риск: {risk.title}'

    def _build_fallback_description(self, risk: ContractRisk) -> str:
        combined = ' '.join([risk.title or '', risk.description or '']).lower()
        section_hint = f" в разделе «{risk.section_name}»" if risk.section_name else ''

        if 'предмет' in combined:
            return (
                f"Уточните у пользователя точный предмет договора{section_hint}: что именно является товаром, работой, "
                "услугой или объектом, в каком объеме/количестве и с какими характеристиками. "
                "Не подставляйте эти данные автоматически без подтверждения."
            )
        if 'спецификац' in combined:
            return (
                f"Подготовьте и подпишите все спецификации{section_hint}, чтобы предмет, качество, количество "
                "и иные существенные условия были определены однозначно."
            )
        if 'оплат' in combined:
            return (
                f"Закрепите конкретные сроки, порядок и условия оплаты{section_hint}, чтобы исключить кассовые разрывы "
                "и споры о моменте исполнения обязательства."
            )
        if 'пролонгац' in combined:
            return (
                f"Пересмотрите механизм автоматической пролонгации{section_hint}: ограничьте число продлений "
                "или добавьте более гибкий порядок отказа."
            )
        if 'односторон' in combined and 'отказ' in combined:
            return (
                f"Уберите безусловное право контрагента на отказ от товара{section_hint} либо свяжите его "
                "с компенсацией расходов Поставщика и четкими основаниями."
            )
        if 'срок' in combined or 'дата' in combined:
            return (
                f"Пропишите конкретные даты, периоды или событие-триггер исполнения{section_hint}, "
                "чтобы убрать неопределенность при поставке, оплате или приемке."
            )

        risk_type = (risk.risk_type or 'general').lower()
        if risk_type == 'financial':
            return (
                f"Уточните денежные условия{section_hint}: лимиты ответственности, порядок расчётов, сроки оплаты "
                "и основания для списаний или удержаний."
            )
        if risk_type == 'legal':
            return (
                f"Перепишите спорную формулировку{section_hint} так, чтобы права и обязанности сторон были определены "
                "однозначно и соответствовали применимому праву."
            )
        if risk_type == 'operational':
            return (
                f"Детализируйте порядок действий сторон{section_hint}: сроки, этапы, уведомления, документы "
                "и распределение ответственности."
            )

        return (
            f"Пересмотрите формулировку{section_hint} и устраните выявленную неопределённость, "
            "чтобы снизить вероятность спора при исполнении договора."
        )

    def generate_suggested_changes(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any],
        required_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ContractSuggestedChange]:
        """
        Generate specific text changes to fix identified risks

        Args:
            xml_content: Raw XML content (for reference)
            structure: Contract structure with sections
            risks: Identified risks
            recommendations: Generated recommendations
            rag_context: Legal context and references

        Returns:
            List of ContractSuggestedChange objects
        """
        try:
            prompt = self._build_suggested_changes_prompt(
                structure, risks, rag_context, required_fields
            )

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_format="json",
                temperature=0.4
            )

            changes_data = response if isinstance(response, dict) else json.loads(response)

            changes = []
            for change_dict in changes_data.get('changes', []):
                try:
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
                except Exception as e:
                    logger.error(f"Failed to create suggested change object: {e}")
                    continue

            logger.info(f"✓ Generated {len(changes)} suggested changes")
            return changes

        except Exception as e:
            logger.error(f"Suggested changes generation failed: {e}")
            return []

    def generate_annotations(
        self,
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        suggested_changes: List[ContractSuggestedChange]
    ) -> List[ContractAnnotation]:
        """
        Generate annotations for document sections

        Creates visual markers for:
        - Critical risks (red highlights)
        - Warnings (yellow highlights)
        - Suggestions (yellow highlights)

        Args:
            risks: List of risks to annotate
            recommendations: List of recommendations
            suggested_changes: List of suggested changes

        Returns:
            List of ContractAnnotation objects
        """
        annotations = []

        # Add risk annotations
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

        # Add suggested change annotations
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

        logger.info(f"✓ Generated {len(annotations)} annotations")
        return annotations

    def _build_recommendations_prompt(
        self,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any],
        company_conditions: list = None,
        required_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build prompt for recommendations generation"""
        prompt = "На основе выявленных рисков сгенерируй рекомендации. Все ответы ТОЛЬКО на русском языке.\n\n"

        prompt += "ВЫЯВЛЕННЫЕ РИСКИ:\n"
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
            prompt += "ПРАВОВОЙ КОНТЕКСТ:\n"
            prompt += rag_context['context'][:5000]
            prompt += "\n\n"

        if required_fields:
            prompt += "ДАННЫЕ, КОТОРЫЕ НУЖНО ЗАПРОСИТЬ У ПОЛЬЗОВАТЕЛЯ:\n"
            prompt += json.dumps([
                {
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'snippet': item.get('snippet', ''),
                    'user_question': item.get('user_question', ''),
                    'missing_data_points': item.get('missing_data_points', []),
                }
                for item in required_fields[:30]
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

        # Add company conditions context
        if company_conditions:
            prompt += "СТАНДАРТЫ КОМПАНИИ (обязательные условия заказчика):\n"
            for cond in company_conditions:
                priority_label = {1: 'низкий', 2: 'средний', 3: 'высокий'}.get(cond.get('priority', 1), '')
                prompt += f"- [{cond.get('category', 'other')}] (приоритет: {priority_label}) {cond.get('title', '')}: {cond.get('condition_text', '')}\n"
            prompt += "\nВАЖНО: Если какой-то риск связан с несоответствием стандартам компании, рекомендация ДОЛЖНА содержать конкретное указание, как привести пункт в соответствие со стандартом.\n\n"

        prompt += """Сгенерируй рекомендации для каждого риска. Все тексты ТОЛЬКО на русском языке.

ВАЖНО:
- Если для исправления пункта не хватает фактических данных, не придумывай значения и не пиши готовую
  финальную формулировку с вымышленными условиями.
- В таких случаях рекомендация должна прямо говорить: какие данные нужно запросить у пользователя и зачем.
- Если проблема связана с предметом договора, рекомендация должна требовать уточнить предмет, объем,
  количество, характеристики или спецификацию, а не фантазировать их.

Верни JSON:
{
  "recommendations": [
    {
      "category": "legal_compliance|risk_mitigation|financial_optimization|company_standard|etc",
      "priority": "critical|high|medium|low",
      "title": "Краткое название рекомендации на русском",
      "description": "Что нужно сделать (на русском)",
      "reasoning": "Почему эта рекомендация важна (на русском)",
      "expected_benefit": "Ожидаемый результат (на русском)",
      "related_risk_id": 0,
      "related_condition": "Название стандарта компании (если применимо)",
      "implementation_complexity": "easy|medium|hard"
    }
  ]
}

Верни ТОЛЬКО валидный JSON."""

        return prompt

    def _build_suggested_changes_prompt(
        self,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        rag_context: Dict[str, Any],
        required_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build prompt for suggested changes generation"""
        prompt = "Сгенерируй конкретные текстовые изменения для исправления выявленных рисков. Все тексты ТОЛЬКО на русском языке.\n\n"

        prompt += "РИСКИ:\n"
        prompt += json.dumps([
            {'id': i, 'title': r.title, 'description': r.description, 'xpath': r.xpath_location}
            for i, r in enumerate(risks)
        ], ensure_ascii=False, indent=2)
        prompt += "\n\n"

        prompt += "РАЗДЕЛЫ ДОГОВОРА:\n"
        prompt += json.dumps(structure.get('sections', [])[:20], ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "ПРАВОВЫЕ ССЫЛКИ:\n"
            prompt += rag_context['context'][:5000]
            prompt += "\n\n"

        if required_fields:
            prompt += "ДАННЫЕ, КОТОРЫЕ НУЖНО ЗАПРОСИТЬ У ПОЛЬЗОВАТЕЛЯ, А НЕ ВЫДУМЫВАТЬ:\n"
            prompt += json.dumps([
                {
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'snippet': item.get('snippet', ''),
                    'user_question': item.get('user_question', ''),
                    'missing_data_points': item.get('missing_data_points', []),
                }
                for item in required_fields[:30]
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

        prompt += """Для каждого риска, который можно исправить изменением текста договора, предложи конкретные правки. Все тексты ТОЛЬКО на русском языке.

ВАЖНО:
- Не выдумывай предмет договора, количество, цену, сроки, реквизиты, идентификаторы, спецификации и иные
  фактические данные, которых нет в документе.
- Если для правки не хватает пользовательских данных, не создавай suggested_text с вымышленными значениями.
- В таких случаях лучше не предлагать текстовую замену, а дождаться данных от пользователя.

{
  "changes": [
    {
      "xpath_location": "XPath к разделу",
      "section_name": "Название раздела",
      "original_text": "Текущий проблемный текст",
      "suggested_text": "Улучшенная версия",
      "change_type": "addition|modification|deletion|clarification",
      "issue": "В чём проблема (на русском)",
      "reasoning": "Почему это изменение решает проблему (на русском)",
      "legal_basis": "Ссылка на закон/статью если применимо",
      "related_risk_id": 0
    }
  ]
}

Верни ТОЛЬКО валидный JSON."""

        return prompt


__all__ = ['RecommendationGenerator']
