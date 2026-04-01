# -*- coding: utf-8 -*-
"""
Risk Analyzer - Identify and assess contract risks

Анализирует риски в договорах с учётом текущей даты, интересов выбранной
стороны и правил фильтрации ложных срабатываний.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import Any, Dict, List, Optional

from loguru import logger

from ..models.analyzer_models import ContractRisk
from ..services.llm_gateway import LLMGateway


class RiskAnalyzer:
    """
    Analyzes contract clauses to identify risks.

    Supports:
    - Batch clause analysis
    - Individual deep analysis
    - RAG-enhanced risk identification
    - Multiple risk types (financial, legal, operational, reputational)
    """

    MAX_PROMPT_CHARS = 120_000

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def analyze_clauses_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]] = None,
        batch_size: int = 15,
        parallel: bool = True,
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze clauses with adaptive batching and optional parallel execution."""
        if not clauses:
            return []

        total_chars = sum(len(c.get("text", "")[:500]) + len(c.get("title", "")) + 30 for c in clauses)
        logger.info(
            f"Total clauses: {len(clauses)}, estimated chars: {total_chars}, limit: {self.MAX_PROMPT_CHARS}"
        )

        max_clauses_per_batch = max(1, min(batch_size, 20))
        if total_chars <= self.MAX_PROMPT_CHARS:
            clauses_per_batch = min(len(clauses), max_clauses_per_batch)
        else:
            avg_chars = max(1, total_chars // len(clauses))
            clauses_per_batch = min(max(5, int(self.MAX_PROMPT_CHARS / avg_chars)), max_clauses_per_batch)

        if clauses_per_batch >= len(clauses):
            logger.info(f"All {len(clauses)} clauses fit into one LLM call")
            try:
                return self._analyze_batch(clauses, rag_context, analysis_context)
            except Exception as exc:
                logger.error(f"Single-call analysis failed: {exc}")
                return [self._get_fallback_analysis(clause) for clause in clauses]

        batches = []
        for index in range(0, len(clauses), clauses_per_batch):
            batches.append((index, clauses[index:index + clauses_per_batch]))

        if not parallel or len(batches) == 1:
            all_analyses: List[Dict[str, Any]] = []
            for batch_index, batch_clauses in batches:
                logger.info(
                    f"Sequential clause analysis batch {batch_index // clauses_per_batch + 1}: "
                    f"{len(batch_clauses)} clauses"
                )
                try:
                    all_analyses.extend(
                        self._analyze_batch(batch_clauses, rag_context, analysis_context)
                    )
                except Exception as exc:
                    logger.error(f"Sequential batch analysis failed: {exc}")
                    all_analyses.extend(self._get_fallback_analysis(c) for c in batch_clauses)
            return all_analyses

        num_batches = len(batches)
        results_map: Dict[int, List[Dict[str, Any]]] = {}
        max_workers = min(num_batches, 3)

        def _process_batch(batch_idx: int, batch_clauses: List[Dict[str, Any]]):
            logger.info(f"[Thread] Batch {batch_idx + 1}/{num_batches}: {len(batch_clauses)} clauses")
            try:
                return batch_idx, self._analyze_batch(batch_clauses, rag_context, analysis_context)
            except Exception as exc:
                logger.error(f"[Thread] Batch {batch_idx + 1} failed: {exc}")
                return batch_idx, [self._get_fallback_analysis(c) for c in batch_clauses]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_batch, idx, batch): idx
                for idx, (_, batch) in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_idx, analyses = future.result()
                results_map[batch_idx] = analyses

        ordered: List[Dict[str, Any]] = []
        for batch_idx in sorted(results_map.keys()):
            ordered.extend(results_map[batch_idx])

        logger.info(f"All {num_batches} batches completed: {len(ordered)} clause analyses")
        return ordered

    def analyze_clause_detailed(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]] = None,
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform detailed analysis of a single clause."""
        try:
            prompt = self._build_detailed_analysis_prompt(clause, rag_context, analysis_context)
            response = self.llm.call(
                prompt=prompt,
                system_prompt=(
                    "Ты — эксперт по анализу рисков в договорах. "
                    "Все ответы давай ТОЛЬКО на русском языке. Формат ответа — JSON."
                ),
                temperature=0.0,
                max_tokens=2000,
                response_format="json",
            )
            analysis = response if isinstance(response, dict) else json.loads(response)
            analysis["clause_id"] = clause["id"]
            analysis["clause_xpath"] = clause.get("xpath", "")
            analysis.setdefault("required_fields", [])
            return analysis
        except Exception as exc:
            logger.error(f"Detailed analysis failed for clause {clause['id']}: {exc}")
            return self._get_fallback_analysis(clause)

    def identify_risks(self, analyses: List[Dict[str, Any]]) -> List[ContractRisk]:
        """Extract and structure risks from clause analyses."""
        risks: List[ContractRisk] = []
        allowed_types = {"financial", "legal", "operational", "reputational", "general"}
        allowed_severities = {"critical", "high", "medium", "low", "info"}
        allowed_prob = {"high", "medium", "low"}

        for analysis in analyses:
            for risk_data in analysis.get("risks", []):
                try:
                    raw_type = (risk_data.get("risk_type") or risk_data.get("type") or "legal").lower()
                    raw_severity = (risk_data.get("severity") or "medium").lower()
                    raw_probability = (risk_data.get("probability") or "medium").lower()

                    risk = ContractRisk(
                        risk_type=raw_type if raw_type in allowed_types else "legal",
                        severity=raw_severity if raw_severity in allowed_severities else "medium",
                        probability=raw_probability if raw_probability in allowed_prob else "medium",
                        title=risk_data.get("title", risk_data.get("description", "Риск")[:255]),
                        description=risk_data.get("description", ""),
                        consequences=risk_data.get("consequences", risk_data.get("impact", "")),
                        xpath_location=analysis.get("clause_xpath", ""),
                        section_name=analysis.get("clause_id", ""),
                    )
                    risks.append(risk)
                except Exception as exc:
                    logger.error(f"Failed to create risk object: {exc}")

        logger.info(f"Identified {len(risks)} total risks")
        return risks

    def _analyze_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]],
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze a clause batch."""
        prompt = self._build_batch_analysis_prompt(clauses, rag_context, analysis_context)
        max_tokens = min(max(4000, len(clauses) * 300), 8000)
        logger.info(
            f"_analyze_batch: {len(clauses)} clauses, max_tokens={max_tokens}, prompt_len={len(prompt)}"
        )

        try:
            response = self.llm.call(
                prompt=prompt,
                system_prompt=(
                    "Ты — эксперт по анализу договоров. "
                    "Выявляй только юридически и коммерчески значимые риски. "
                    "Все ответы давай ТОЛЬКО на русском языке. Формат ответа — JSON."
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                response_format="json",
            )
        except Exception as llm_err:
            logger.error(f"LLM call failed in _analyze_batch: {type(llm_err).__name__}: {llm_err}")
            raise

        try:
            result = response if isinstance(response, dict) else json.loads(response)
            analyses = result.get("analyses", [])
            while len(analyses) < len(clauses):
                analyses.append(self._get_fallback_analysis(clauses[len(analyses)]))
            for idx, analysis in enumerate(analyses):
                analysis.setdefault("clause_number", idx + 1)
                analysis.setdefault("required_fields", [])
            return analyses
        except (json.JSONDecodeError, AttributeError) as exc:
            logger.error(f"JSON decode failed: {exc}")
            return [self._get_fallback_analysis(clause) for clause in clauses]

    @staticmethod
    def _build_analysis_directives(analysis_context: Optional[Dict[str, Any]]) -> str:
        if not analysis_context:
            return ""

        lines = []
        analysis_date = analysis_context.get("analysis_date")
        analysis_perspective = analysis_context.get("analysis_perspective")

        if analysis_date:
            lines.append(f"- Текущая дата анализа: {analysis_date}. Оценивай все даты относительно этой даты.")
        if analysis_perspective:
            lines.append(
                f"- Анализируй договор в пользу и в интересах этой стороны: {analysis_perspective}."
            )

        lines.append(
            "- Не считай рисками служебные метаданные файла или парсинга: file_name, UUID, parsed_at, "
            "author, title метаданных DOCX и другие технические поля вне текста договора."
        )
        lines.append(
            "- Незаполненные поля, пропуски, шаблонные подстановки вида ___, [указать ...], "
            "[заполнить ...] не являются рисками сами по себе. Возвращай их только в required_fields."
        )
        return "\n".join(lines)

    def _build_batch_analysis_prompt(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]],
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for batch analysis."""
        clauses_text = "\n\n".join([
            f"ПУНКТ {idx + 1} [{clause['type']}]:\n"
            f"Заголовок: {clause['title']}\n"
            f"Текст: {clause['text'][:500]}"
            for idx, clause in enumerate(clauses)
        ])

        rag_info = ""
        if rag_context:
            rag_info = f"\n\nРЕЛЕВАНТНЫЕ ПРЕЦЕДЕНТЫ:\n{rag_context.get('precedents', '')[:500]}"
            rag_info += f"\n\nПРАВОВЫЕ НОРМЫ:\n{rag_context.get('norms', '')[:500]}"

        directives = self._build_analysis_directives(analysis_context)
        directives_block = f"\n\nОБЯЗАТЕЛЬНЫЕ ПРАВИЛА АНАЛИЗА:\n{directives}" if directives else ""

        return f"""Проанализируй следующие пункты договора на наличие рисков.

{clauses_text}{rag_info}{directives_block}

Для каждого пункта:
1. Выдели только реальные юридические, финансовые, операционные и репутационные риски.
2. Если в пункте есть только незаполненное поле или шаблонный пропуск, не создавай риск.
3. Такие места перечисляй отдельно в required_fields.

Верни JSON:
{{
  "analyses": [
    {{
      "clause_number": 1,
      "risks": [
        {{
          "type": "financial|legal|operational|reputational|general",
          "severity": "critical|high|medium|low|info",
          "probability": "high|medium|low",
          "title": "Краткое название риска на русском",
          "description": "Подробное описание риска на русском",
          "consequences": "Последствия на русском",
          "impact": "Анализ влияния на русском",
          "mitigation": "Как снизить риск на русском",
          "legal_basis": "Ссылки на закон или практику"
        }}
      ],
      "issues": ["Краткое описание проблем пункта на русском"],
      "required_fields": [
        {{
          "title": "Что нужно заполнить",
          "description": "Почему это поле нужно заполнить",
          "snippet": "Фрагмент с пропуском"
        }}
      ],
      "overall_risk_level": "critical|high|medium|low|info"
    }}
  ]
}}

Верни ТОЛЬКО валидный JSON."""

    def _build_detailed_analysis_prompt(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]],
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for detailed single-clause analysis."""
        rag_info = ""
        if rag_context:
            rag_info = (
                f"\n\nРЕЛЕВАНТНЫЙ КОНТЕКСТ:\n"
                f"Прецеденты: {rag_context.get('precedents', '')[:300]}\n"
                f"Нормы: {rag_context.get('norms', '')[:300]}"
            )

        directives = self._build_analysis_directives(analysis_context)
        directives_block = f"\n\nОБЯЗАТЕЛЬНЫЕ ПРАВИЛА АНАЛИЗА:\n{directives}" if directives else ""

        return f"""Выполни глубокий анализ этого пункта договора:

ПУНКТ: {clause['title']}
ТИП: {clause['type']}
ТЕКСТ: {clause['text']}{rag_info}{directives_block}

Верни JSON:
{{
  "risks": [
    {{
      "type": "financial|legal|operational|reputational|general",
      "severity": "critical|high|medium|low|info",
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
  "required_fields": [
    {{
      "title": "Что нужно заполнить",
      "description": "Почему это поле обязательно заполнить",
      "snippet": "Фрагмент с пропуском"
    }}
  ],
  "strengths": ["сильные стороны на русском"],
  "weaknesses": ["слабые стороны на русском"],
  "recommendations": ["рекомендации на русском"],
  "overall_risk_level": "critical|high|medium|low|info"
}}

Верни ТОЛЬКО валидный JSON."""

    def _get_fallback_analysis(self, clause: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis if LLM fails."""
        return {
            "clause_number": clause.get("number", 0),
            "clause_id": clause.get("id", ""),
            "risks": [],
            "issues": [],
            "required_fields": [],
            "overall_risk_level": "unknown",
            "error": "Analysis failed - fallback used",
        }


__all__ = ["RiskAnalyzer"]
