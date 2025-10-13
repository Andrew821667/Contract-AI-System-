# -*- coding: utf-8 -*-
"""
Change Report Generator - Generate PDF reports for contract changes
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from loguru import logger


class ChangeReportGenerator:
    """
    Generator for PDF reports of contract changes

    Features:
    - Executive summary
    - Detailed change analysis
    - Statistics and charts
    - Recommendations

    Note: This is a stub. Real implementation would use reportlab or weasyprint
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = self.config.get('output_dir', 'data/reports')
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(
        self,
        analysis_result: Dict[str, Any],
        changes: List[Dict[str, Any]],
        output_filename: Optional[str] = None
    ) -> str:
        """
        Generate PDF report for change analysis

        Args:
            analysis_result: ChangeAnalysisResult data
            changes: List of ContractChange data
            output_filename: Optional custom filename

        Returns:
            Path to generated PDF
        """
        try:
            logger.info("Generating change analysis report")

            if not output_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"change_report_{timestamp}.pdf"

            output_path = os.path.join(self.output_dir, output_filename)

            # Stub: Generate text report instead of PDF
            report_content = self._generate_text_report(analysis_result, changes)

            # Save as text (stub)
            with open(output_path.replace('.pdf', '.txt'), 'w', encoding='utf-8') as f:
                f.write(report_content)

            logger.info(f"Report generated: {output_path}")
            logger.warning("[STUB] PDF generation not fully implemented - saved as .txt")

            return output_path.replace('.pdf', '.txt')

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise

    def _generate_text_report(
        self,
        analysis_result: Dict[str, Any],
        changes: List[Dict[str, Any]]
    ) -> str:
        """
        Generate text version of report (stub for PDF)

        Real implementation would use reportlab:
        ```python
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch

        pdf = SimpleDocTemplate(output_path, pagesize=A4)
        story = []

        # Add title
        styles = getSampleStyleSheet()
        title = Paragraph("Contract Change Analysis Report", styles['Title'])
        story.append(title)

        # Add summary
        # Add statistics table
        # Add detailed changes
        # Add recommendations

        pdf.build(story)
        ```
        """
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("ОТЧЁТ ОБ ИЗМЕНЕНИЯХ В ДОГОВОРЕ")
        lines.append("=" * 80)
        lines.append(f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("")

        # Executive Summary
        lines.append("РЕЗЮМЕ")
        lines.append("-" * 80)
        lines.append(f"Общая оценка: {analysis_result.get('overall_assessment', 'N/A')}")
        lines.append(f"Изменение рисков: {analysis_result.get('overall_risk_change', 'N/A')}")
        lines.append(f"Всего изменений: {analysis_result.get('total_changes', 0)}")
        lines.append("")

        if analysis_result.get('executive_summary'):
            lines.append(analysis_result['executive_summary'])
            lines.append("")

        # Statistics
        lines.append("СТАТИСТИКА")
        lines.append("-" * 80)

        by_type = analysis_result.get('by_type', {})
        if by_type:
            lines.append("По типам:")
            for change_type, count in by_type.items():
                lines.append(f"  - {change_type}: {count}")
            lines.append("")

        by_impact = analysis_result.get('by_impact', {})
        if by_impact:
            lines.append("По влиянию:")
            for impact, count in by_impact.items():
                lines.append(f"  - {impact}: {count}")
            lines.append("")

        # Disagreement tracking
        if analysis_result.get('accepted_objections', 0) > 0:
            lines.append("ПРИНЯТЫЕ ВОЗРАЖЕНИЯ")
            lines.append("-" * 80)
            lines.append(f"Принято: {analysis_result.get('accepted_objections', 0)}")
            lines.append(f"Отклонено: {analysis_result.get('rejected_objections', 0)}")
            lines.append(f"Частично: {analysis_result.get('partial_objections', 0)}")
            lines.append("")

        # Critical changes
        critical = analysis_result.get('critical_changes', [])
        if critical:
            lines.append("КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ")
            lines.append("-" * 80)
            for i, change_id in enumerate(critical, 1):
                # Find change by ID
                change = next((c for c in changes if c.get('id') == change_id), None)
                if change:
                    lines.append(f"{i}. {change.get('semantic_description', 'N/A')}")
                    lines.append(f"   Раздел: {change.get('section_name', 'N/A')}")
                    lines.append("")

        # Detailed changes
        lines.append("ДЕТАЛЬНЫЙ АНАЛИЗ ИЗМЕНЕНИЙ")
        lines.append("-" * 80)

        for i, change in enumerate(changes[:20], 1):  # Limit to 20 for stub
            lines.append(f"{i}. {change.get('change_type', 'N/A').upper()}")
            lines.append(f"   Раздел: {change.get('section_name', 'N/A')}")
            lines.append(f"   Категория: {change.get('change_category', 'N/A')}")

            if change.get('semantic_description'):
                lines.append(f"   Описание: {change['semantic_description']}")

            impact = change.get('impact_assessment', {})
            if impact:
                lines.append(f"   Влияние: {impact.get('direction', 'N/A')} ({impact.get('severity', 'N/A')})")
                if impact.get('recommendation'):
                    lines.append(f"   Рекомендация: {impact['recommendation']}")

            lines.append("")

        # Recommendations
        if analysis_result.get('recommendations'):
            lines.append("РЕКОМЕНДАЦИИ")
            lines.append("-" * 80)
            lines.append(analysis_result['recommendations'])
            lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("Отчёт создан автоматически системой Contract AI")
        lines.append("=" * 80)

        return "\n".join(lines)


__all__ = ["ChangeReportGenerator"]
