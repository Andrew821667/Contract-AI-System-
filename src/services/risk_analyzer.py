# -*- coding: utf-8 -*-
"""
Risk Analyzer - Identify and assess contract risks

Анализирует риски в договорах используя LLM и RAG
"""
from typing import Dict, Any, List, Optional
import json
from loguru import logger

from ..services.llm_gateway import LLMGateway
from ..models.analyzer_models import ContractRisk


class RiskAnalyzer:
    """
    Analyzes contract clauses to identify risks

    Supports:
    - Batch clause analysis
    - Individual deep analysis
    - RAG-enhanced risk identification
    - Multiple risk types (financial, legal, operational, reputational)
    """

    def __init__(self, llm_gateway: LLMGateway):
        """
        Initialize risk analyzer

        Args:
            llm_gateway: LLM gateway for analysis
        """
        self.llm = llm_gateway

    def analyze_full_text(
        self,
        plain_text: str,
        rag_context: Optional[Dict[str, Any]] = None,
        company_conditions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Полнотекстовый анализ договора — отправка ВСЕГО текста в LLM.

        Проход 1 двухпроходного анализа: LLM видит весь документ целиком
        и может выявить системные риски, взаимосвязи между разделами,
        пропущенные условия и баланс прав/обязанностей.

        Args:
            plain_text: Полный текст договора (plain text, без XML-тегов)
            rag_context: Контекст из RAG (прецеденты, нормы)
            company_conditions: Стандарты компании пользователя

        Returns:
            Dict с ключами: risks, compliance_issues, missing_clauses,
            balance_assessment, dispute_forecast, summary
        """
        estimated_tokens = len(plain_text) // 4
        logger.info(f"Full-text analysis: {len(plain_text)} chars (~{estimated_tokens} tokens)")

        # RAG context
        rag_block = ""
        if rag_context:
            precedents = rag_context.get('precedents', '')
            norms = rag_context.get('norms', '')
            if precedents:
                rag_block += f"\n\nСУДЕБНАЯ ПРАКТИКА И ПРЕЦЕДЕНТЫ:\n{precedents[:5000]}"
            if norms:
                rag_block += f"\n\nПРАВОВЫЕ НОРМЫ:\n{norms[:5000]}"

        # Company conditions
        conditions_block = ""
        if company_conditions:
            conditions_lines = []
            for cond in company_conditions:
                priority_label = {1: 'низкий', 2: 'средний', 3: 'высокий'}.get(cond.get('priority', 1), '')
                conditions_lines.append(
                    f"- [{cond.get('category', 'other')}] (приоритет: {priority_label}) "
                    f"{cond.get('title', '')}: {cond.get('condition_text', '')}"
                )
            conditions_block = f"\n\nСТАНДАРТЫ КОМПАНИИ:\n" + "\n".join(conditions_lines)

        prompt = f"""Проведи ПОЛНЫЙ КОМПЛЕКСНЫЙ анализ договора.
Ты видишь ВЕСЬ текст — анализируй взаимосвязи между разделами, баланс прав и обязанностей,
пропущенные условия и системные риски.

ПОЛНЫЙ ТЕКСТ ДОГОВОРА:
{plain_text}{rag_block}{conditions_block}

ЗАДАЧА:
1. Выяви ВСЕ риски с учётом взаимосвязей между разделами
2. Проверь соответствие стандартам компании (если заданы)
3. Оцени баланс прав и обязанностей сторон
4. Найди ПРОПУЩЕННЫЕ важные условия (которых нет, но должны быть)
5. Дай прогноз вероятности споров с обоснованием
6. Составь краткое резюме договора (2-3 предложения)

ВАЖНО: Все ответы ТОЛЬКО на русском языке.

Верни JSON:
{{
  "risks": [
    {{
      "type": "financial|legal|operational|reputational|compliance",
      "severity": "critical|high|medium|low",
      "probability": "high|medium|low",
      "title": "Краткое название риска",
      "description": "Подробное описание",
      "consequences": "Возможные последствия",
      "mitigation": "Стратегия снижения",
      "legal_basis": "Ссылки на законы/статьи",
      "related_sections": ["Раздел 1", "Раздел 5"],
      "related_condition": "Название стандарта (если применимо)"
    }}
  ],
  "compliance_issues": [
    {{
      "condition_title": "Название стандарта",
      "status": "non_compliant|partial",
      "description": "В чём несоответствие",
      "recommendation": "Что изменить"
    }}
  ],
  "missing_clauses": [
    {{
      "title": "Название пропущенного условия",
      "importance": "critical|high|medium",
      "description": "Почему это важно",
      "suggested_text": "Рекомендуемая формулировка"
    }}
  ],
  "balance_assessment": {{
    "score": 0.0-1.0,
    "description": "Оценка баланса прав и обязанностей",
    "party_advantages": {{"сторона": "описание преимуществ"}}
  }},
  "dispute_forecast": {{
    "probability": 0.0-1.0,
    "key_triggers": ["потенциальные причины споров"],
    "recommendation": "Как снизить вероятность"
  }},
  "summary": "Краткое резюме договора (2-3 предложения)"
}}"""

        try:
            response = self.llm.call(
                prompt=prompt,
                system_prompt=(
                    "Ты — ведущий эксперт по анализу договоров, специализирующийся на российском праве. "
                    "Ты проводишь глубокий комплексный анализ ВСЕГО текста договора. "
                    "Все ответы давай ТОЛЬКО на русском языке. Формат — JSON."
                ),
                temperature=0.0,
                max_tokens=16000,
                response_format="json"
            )

            result = json.loads(response) if isinstance(response, str) else response
            logger.info(
                f"Full-text analysis complete: {len(result.get('risks', []))} risks, "
                f"{len(result.get('missing_clauses', []))} missing clauses"
            )
            return result

        except Exception as e:
            logger.error(f"Full-text analysis failed: {e}")
            return {
                'risks': [],
                'compliance_issues': [],
                'missing_clauses': [],
                'balance_assessment': {'score': 0.5, 'description': 'Анализ не удался'},
                'dispute_forecast': {'probability': 0.5, 'key_triggers': [], 'recommendation': ''},
                'summary': 'Полнотекстовый анализ не удался, используются результаты поклаузульного анализа.',
                'error': str(e)
            }

    def analyze_clauses_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]] = None,
        batch_size: int = 15,
        parallel: bool = True,
        company_conditions: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple clauses in batches (optionally parallel).

        Args:
            clauses: List of clause dicts
            rag_context: Optional RAG context with precedents/norms
            batch_size: Clauses per batch (default: 15)
            parallel: Run batches in parallel using threads (default: True)
            company_conditions: Optional list of user's company standard conditions

        Returns:
            List of clause analyses with risks
        """
        # Split into batches
        batches = []
        for i in range(0, len(clauses), batch_size):
            batches.append((i, clauses[i:i + batch_size]))

        if not batches:
            return []

        from config.settings import settings
        max_concurrent = getattr(settings, 'max_concurrent_batches', 3)

        if parallel and len(batches) > 1:
            return self._analyze_batches_parallel(batches, rag_context, max_concurrent, company_conditions)

        # Sequential fallback
        all_analyses: List[Dict[str, Any]] = []
        for i, batch in batches:
            logger.info(f"Analyzing batch {i//batch_size + 1}: clauses {i+1}-{i+len(batch)}")
            try:
                batch_analyses = self._analyze_batch(batch, rag_context, company_conditions)
                all_analyses.extend(batch_analyses)
            except Exception as e:
                logger.error(f"Batch analysis failed: {e}")
                for clause in batch:
                    all_analyses.append(self._get_fallback_analysis(clause))
        return all_analyses

    def _analyze_batches_parallel(
        self,
        batches: List,
        rag_context: Optional[Dict[str, Any]],
        max_concurrent: int = 3,
        company_conditions: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Run batch analyses in parallel using ThreadPoolExecutor"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results_map: Dict[int, List[Dict[str, Any]]] = {}

        def process_batch(batch_idx, batch_clauses):
            logger.info(f"[Parallel] Analyzing batch {batch_idx + 1}: {len(batch_clauses)} clauses")
            try:
                return batch_idx, self._analyze_batch(batch_clauses, rag_context, company_conditions)
            except Exception as e:
                logger.error(f"[Parallel] Batch {batch_idx + 1} failed: {e}", exc_info=True)
                return batch_idx, [self._get_fallback_analysis(c) for c in batch_clauses]

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {
                executor.submit(process_batch, idx, batch): idx
                for idx, (_, batch) in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_idx, analyses = future.result()
                results_map[batch_idx] = analyses

        # Reassemble in order
        all_analyses = []
        for idx in sorted(results_map.keys()):
            all_analyses.extend(results_map[idx])

        logger.info(f"[Parallel] All {len(batches)} batches completed: {len(all_analyses)} clause analyses")
        return all_analyses

    def analyze_clause_detailed(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform detailed analysis of single clause

        Args:
            clause: Clause dict with text, type, xpath
            rag_context: Optional RAG context

        Returns:
            Detailed analysis with risks, recommendations
        """
        try:
            prompt = self._build_detailed_analysis_prompt(clause, rag_context)

            response = self.llm.call(
                prompt=prompt,
                system_prompt="Ты — эксперт по анализу рисков в договорах. Все ответы давай ТОЛЬКО на русском языке. Формат ответа — JSON.",
                temperature=0.0,
                max_tokens=2000,
                response_format="json"
            )

            analysis = json.loads(response) if isinstance(response, str) else response
            analysis['clause_id'] = clause['id']
            analysis['clause_xpath'] = clause.get('xpath', '')

            return analysis

        except Exception as e:
            logger.error(f"Detailed analysis failed for clause {clause['id']}: {e}")
            return self._get_fallback_analysis(clause)

    def identify_risks(
        self,
        analyses: List[Dict[str, Any]]
    ) -> List[ContractRisk]:
        """
        Extract and structure risks from analyses

        Args:
            analyses: List of clause analyses

        Returns:
            List of ContractRisk objects
        """
        risks: List[ContractRisk] = []

        for analysis in analyses:
            clause_risks = analysis.get('risks', [])

            for risk_data in clause_risks:
                try:
                    # Map risk_type to allowed values
                    raw_type = risk_data.get('risk_type', risk_data.get('type', 'legal'))
                    allowed_types = ('financial', 'legal', 'operational', 'reputational', 'compliance')
                    risk_type = raw_type if raw_type in allowed_types else 'legal'

                    # Map severity to allowed values
                    raw_severity = risk_data.get('severity', 'medium')
                    allowed_severities = ('critical', 'high', 'significant', 'medium', 'minor', 'low')
                    severity = raw_severity if raw_severity in allowed_severities else 'medium'

                    # Map probability
                    raw_prob = risk_data.get('probability', 'medium')
                    allowed_prob = ('high', 'medium', 'low')
                    probability = raw_prob if raw_prob in allowed_prob else 'medium'

                    risk = ContractRisk(
                        risk_type=risk_type,
                        severity=severity,
                        probability=probability,
                        title=risk_data.get('title', risk_data.get('description', 'Риск')[:255]),
                        description=risk_data.get('description', ''),
                        consequences=risk_data.get('consequences', risk_data.get('impact', '')),
                        xpath_location=analysis.get('clause_xpath', ''),
                        section_name=analysis.get('clause_id', ''),
                    )
                    risks.append(risk)

                except Exception as e:
                    logger.error(f"Failed to create risk object: {e}")
                    continue

        logger.info(f"Identified {len(risks)} total risks")
        return risks

    def _analyze_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]],
        company_conditions: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Analyze batch of clauses"""
        prompt = self._build_batch_analysis_prompt(clauses, rag_context, company_conditions)

        response = self.llm.call(
            prompt=prompt,
            system_prompt="Ты — эксперт по анализу договоров. Анализируй пункты и выявляй риски. Все ответы давай ТОЛЬКО на русском языке. Формат ответа — JSON.",
            temperature=0.0,
            max_tokens=8000,
            response_format="json"
        )

        try:
            result = json.loads(response) if isinstance(response, str) else response
            analyses = result.get('analyses', [])

            # Ensure we have analysis for each clause
            if len(analyses) < len(clauses):
                logger.warning(f"Expected {len(clauses)} analyses, got {len(analyses)}")
                # Fill missing with fallbacks
                while len(analyses) < len(clauses):
                    analyses.append(self._get_fallback_analysis(clauses[len(analyses)]))

            return analyses

        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"JSON decode failed: {e}")
            return [self._get_fallback_analysis(c) for c in clauses]

    def _build_batch_analysis_prompt(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]],
        company_conditions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build prompt for batch analysis"""
        clauses_text = "\n\n".join([
            f"ПУНКТ {i+1} [{clause['type']}]:\nЗаголовок: {clause['title']}\nТекст: {clause['text']}"
            for i, clause in enumerate(clauses)
        ])

        rag_info = ""
        if rag_context:
            precedents = rag_context.get('precedents', '')
            norms = rag_context.get('norms', '')
            if precedents:
                rag_info += f"\n\nСУДЕБНАЯ ПРАКТИКА:\n{precedents[:3000]}"
            if norms:
                rag_info += f"\n\nПРАВОВЫЕ НОРМЫ:\n{norms[:3000]}"

        # Build company conditions block
        conditions_block = ""
        if company_conditions:
            conditions_lines = []
            for cond in company_conditions:
                priority_label = {1: 'низкий', 2: 'средний', 3: 'высокий'}.get(cond.get('priority', 1), '')
                conditions_lines.append(
                    f"- [{cond.get('category', 'other')}] (приоритет: {priority_label}) "
                    f"{cond.get('title', '')}: {cond.get('condition_text', '')[:300]}"
                )
            conditions_block = f"""

СТАНДАРТЫ КОМПАНИИ (условия, которым должен соответствовать договор):
{chr(10).join(conditions_lines)}

ВАЖНО: Для каждого пункта договора проверь соответствие стандартам компании.
Если пункт НЕ соответствует стандарту — обязательно укажи это как риск типа "compliance"
с описанием, какому именно стандарту он не соответствует и что нужно изменить.
Если пункт соответствует стандарту — укажи это в поле "compliance_status"."""

        prompt = f"""Проанализируй следующие пункты договора на наличие рисков:

{clauses_text}{rag_info}{conditions_block}

Для каждого пункта определи:
1. Риски (тип, серьёзность, вероятность, последствия, меры снижения)
2. Проблемы (соответствие законодательству, ясность формулировок, справедливость условий)
3. Соответствие стандартам компании (если стандарты заданы)

ВАЖНО: Все описания, последствия и рекомендации пиши ТОЛЬКО на русском языке.

Верни JSON:
{{
  "analyses": [
    {{
      "clause_number": 1,
      "risks": [
        {{
          "type": "financial|legal|operational|reputational|compliance",
          "severity": "critical|high|medium|low",
          "probability": "high|medium|low",
          "title": "Краткое название риска на русском",
          "description": "Подробное описание риска на русском",
          "consequences": "Возможные последствия на русском",
          "impact": "Анализ влияния на русском",
          "mitigation": "Стратегия снижения риска на русском",
          "legal_basis": "Ссылки на законы/статьи",
          "related_condition": "Название стандарта компании (если применимо)"
        }}
      ],
      "issues": ["описание проблемы на русском"],
      "compliance_status": "compliant|non_compliant|partial|not_applicable",
      "overall_risk_level": "critical|high|medium|low"
    }}
  ]
}}"""

        return prompt

    def _build_detailed_analysis_prompt(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for detailed single clause analysis"""
        rag_info = ""
        if rag_context:
            precedents = rag_context.get('precedents', '')
            norms = rag_context.get('norms', '')
            if precedents:
                rag_info += f"\n\nСУДЕБНАЯ ПРАКТИКА:\n{precedents[:3000]}"
            if norms:
                rag_info += f"\n\nПРАВОВЫЕ НОРМЫ:\n{norms[:3000]}"

        prompt = f"""Выполни глубокий анализ этого пункта договора:

ПУНКТ: {clause['title']}
ТИП: {clause['type']}
ТЕКСТ: {clause['text']}{rag_info}

ВАЖНО: Все описания пиши ТОЛЬКО на русском языке.

Верни подробную оценку рисков в JSON:
{{
  "risks": [
    {{
      "type": "financial|legal|operational|reputational",
      "severity": "critical|high|medium|low",
      "probability": "high|medium|low",
      "title": "Краткое название риска на русском",
      "description": "Подробное описание риска на русском",
      "consequences": "Возможные последствия на русском",
      "impact": "Детальный анализ влияния на русском",
      "mitigation": "Стратегия снижения риска на русском",
      "legal_basis": "Ссылки на законы/статьи",
      "precedents": ["Прецедент 1", "Прецедент 2"]
    }}
  ],
  "strengths": ["сильные стороны на русском"],
  "weaknesses": ["слабые стороны на русском"],
  "recommendations": ["рекомендации на русском"],
  "overall_risk_level": "critical|high|medium|low"
}}"""

        return prompt

    def _get_fallback_analysis(self, clause: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis if LLM fails"""
        return {
            'clause_number': clause.get('number', 0),
            'clause_id': clause.get('id', ''),
            'risks': [],
            'issues': [],
            'overall_risk_level': 'unknown',
            'error': 'Analysis failed - fallback used'
        }


__all__ = ['RiskAnalyzer']
