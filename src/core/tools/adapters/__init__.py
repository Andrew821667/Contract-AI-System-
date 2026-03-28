"""Tool Adapters — обёртки существующих сервисов в ITool интерфейс."""

from .document_parser_tool import DocumentParserTool
from .risk_scorer_tool import RiskScorerTool
from .clause_extractor_tool import ClauseExtractorTool
from .contract_generator_tool import ContractGeneratorTool
from .rag_search_tool import RAGSearchTool
from .complexity_scorer_tool import ComplexityScorerTool
from .counterparty_tool import CounterpartyTool
from .document_diff_tool import DocumentDiffTool
from .smart_composer_tool import SmartComposerTool
from .recommendation_tool import RecommendationTool
from .clause_library_tool import ClauseLibraryTool
from .knowledge_base_tool import KnowledgeBaseTool
from .analytics_tool import AnalyticsTool
from .template_manager_tool import TemplateManagerTool
from .validation_tool import ValidationTool
from .ocr_tool import OCRTool
from .workflow_tool import WorkflowTool

__all__ = [
    "DocumentParserTool",
    "RiskScorerTool",
    "ClauseExtractorTool",
    "ContractGeneratorTool",
    "RAGSearchTool",
    "ComplexityScorerTool",
    "CounterpartyTool",
    "DocumentDiffTool",
    "SmartComposerTool",
    "RecommendationTool",
    "ClauseLibraryTool",
    "KnowledgeBaseTool",
    "AnalyticsTool",
    "TemplateManagerTool",
    "ValidationTool",
    "OCRTool",
    "WorkflowTool",
]
