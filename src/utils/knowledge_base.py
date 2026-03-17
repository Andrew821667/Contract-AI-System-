# -*- coding: utf-8 -*-
"""
Управление базой знаний с категориями
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger


class KnowledgeBaseCategory(Enum):
    """Категории базы знаний"""
    FORMS = "forms"  # Формы договоров
    LEGAL = "legal"  # Нормативная база
    CASE_LAW = "case_law"  # Судебная практика
    KEY_CASES = "key_cases"  # Ключевые кейсы
    TRENDS = "trends"  # Актуальные тенденции


KNOWLEDGE_BASE_CONFIG = {
    KnowledgeBaseCategory.FORMS: {
        "name_ru": "Формы договоров",
        "description": "Типовые формы и шаблоны договоров",
        "collection_name": "contract_forms",
        "icon": "📄",
        "priority": 1,
    },
    KnowledgeBaseCategory.LEGAL: {
        "name_ru": "Нормативная база",
        "description": "ГК РФ, специальные законы, подзаконные акты",
        "collection_name": "legal_base",
        "icon": "⚖️",
        "priority": 2,
    },
    KnowledgeBaseCategory.CASE_LAW: {
        "name_ru": "Судебная практика",
        "description": "Решения ВС РФ, постановления Пленума, обзоры практики",
        "collection_name": "case_law",
        "icon": "🏛️",
        "priority": 3,
    },
    KnowledgeBaseCategory.KEY_CASES: {
        "name_ru": "Ключевые кейсы",
        "description": "Важные прецеденты и разъяснения",
        "collection_name": "key_cases",
        "icon": "⭐",
        "priority": 4,
    },
    KnowledgeBaseCategory.TRENDS: {
        "name_ru": "Актуальные тенденции",
        "description": "Изменения законодательства, новые подходы",
        "collection_name": "trends",
        "icon": "📈",
        "priority": 5,
    }
}


class KnowledgeBaseManager:
    """Менеджер базы знаний"""

    def __init__(self, data_dir: str = "./data/knowledge_base"):
        self.data_dir = Path(data_dir)
        self._ensure_directories()

    def _ensure_directories(self):
        """Создать директории для каждой категории"""
        for category in KnowledgeBaseCategory:
            category_dir = self.data_dir / category.value
            category_dir.mkdir(parents=True, exist_ok=True)

    def get_category_info(self, category: KnowledgeBaseCategory) -> Dict[str, Any]:
        """Получить информацию о категории"""
        return KNOWLEDGE_BASE_CONFIG.get(category, {})

    def get_category_path(self, category: KnowledgeBaseCategory) -> Path:
        """Получить путь к директории категории"""
        return self.data_dir / category.value

    def list_documents(self, category: KnowledgeBaseCategory) -> List[Path]:
        """Получить список документов в категории"""
        category_path = self.get_category_path(category)
        return list(category_path.glob("**/*.txt")) + list(category_path.glob("**/*.md"))

    def get_all_categories_info(self) -> List[Dict[str, Any]]:
        """Получить информацию обо всех категориях"""
        categories = []
        for category in KnowledgeBaseCategory:
            info = self.get_category_info(category)
            doc_count = len(self.list_documents(category))
            categories.append({
                "category": category,
                "info": info,
                "document_count": doc_count
            })
        return sorted(categories, key=lambda x: x['info']['priority'])

    def search_in_category(
        self,
        category: KnowledgeBaseCategory,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск в конкретной категории с интеграцией RAG системы
        """
        try:
            # Import RAG system here to avoid circular imports
            from ..services.rag_system import RAGSystem
            from ..models import get_db

            # Map category to RAG collection
            category_to_collection = {
                KnowledgeBaseCategory.FORMS: RAGSystem.COLLECTION_TEMPLATES,
                KnowledgeBaseCategory.LEGAL: RAGSystem.COLLECTION_LAWS,
                KnowledgeBaseCategory.CASE_LAW: RAGSystem.COLLECTION_CASE_LAW,
                KnowledgeBaseCategory.KEY_CASES: RAGSystem.COLLECTION_CASE_LAW,
                KnowledgeBaseCategory.TRENDS: RAGSystem.COLLECTION_KNOWLEDGE,
            }

            collection = category_to_collection.get(category, RAGSystem.COLLECTION_KNOWLEDGE)

            # Initialize RAG system
            db = next(get_db())
            rag = RAGSystem(db_session=db)

            # Search in collection
            documents = rag.search(
                query=query,
                collection=collection,
                top_k=top_k,
                use_reranking=True
            )

            # Convert to dict format
            results = []
            for doc in documents:
                results.append({
                    'id': doc.doc_id,
                    'content': doc.content,
                    'metadata': doc.metadata,
                    'score': doc.score,
                    'category': category.value
                })

            logger.info(f"Found {len(results)} results in category {category.value}")
            return results

        except Exception as e:
            logger.error(f"Error searching in category {category.value}: {e}")
            return []

    def search_all_categories(
        self,
        query: str,
        categories: Optional[List[KnowledgeBaseCategory]] = None,
        top_k: int = 10
    ) -> Dict[KnowledgeBaseCategory, List[Dict[str, Any]]]:
        """
        Поиск по всем или выбранным категориям
        """
        if categories is None:
            categories = list(KnowledgeBaseCategory)

        results = {}
        for category in categories:
            category_results = self.search_in_category(category, query, top_k)
            if category_results:
                results[category] = category_results

        return results

    def add_document(
        self,
        category: KnowledgeBaseCategory,
        filename: str,
        content: str
    ) -> Path:
        """Добавить документ в базу знаний"""
        category_path = self.get_category_path(category)
        file_path = category_path / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return file_path

    def get_category_statistics(self) -> Dict[str, Any]:
        """Получить статистику по базе знаний"""
        stats = {}
        total_documents = 0

        for category in KnowledgeBaseCategory:
            doc_count = len(self.list_documents(category))
            total_documents += doc_count
            info = self.get_category_info(category)
            stats[category.value] = {
                "name": info.get("name_ru", ""),
                "count": doc_count,
                "icon": info.get("icon", "📄")
            }

        stats["total"] = total_documents
        return stats


# Готовые примеры документов для каждой категории
SAMPLE_DOCUMENTS = {
    KnowledgeBaseCategory.FORMS: [
        {
            "filename": "supply_agreement_template.txt",
            "content": """
Типовая форма договора поставки

1. ПРЕДМЕТ ДОГОВОРА
Поставщик обязуется передать в собственность Покупателя товар, а Покупатель обязуется принять товар и оплатить его.

2. КОЛИЧЕСТВО И АССОРТИМЕНТ ТОВАРА
Определяется спецификацией к настоящему договору.

3. КАЧЕСТВО ТОВАРА
Товар должен соответствовать требованиям ГОСТ/ТУ и иметь сертификаты соответствия.

4. ЦЕНА И ПОРЯДОК РАСЧЕТОВ
4.1. Цена товара определяется спецификацией.
4.2. Оплата производится в течение ___ дней с момента поставки.

5. СРОК И ПОРЯДОК ПОСТАВКИ
5.1. Поставка осуществляется партиями согласно графику поставки.
5.2. Место поставки: ___________.

6. ОТВЕТСТВЕННОСТЬ СТОРОН
6.1. За просрочку поставки - пеня 0.1% от стоимости за каждый день просрочки.
6.2. За просрочку оплаты - пеня 0.1% от суммы задолженности за каждый день просрочки.
"""
        }
    ],
    KnowledgeBaseCategory.LEGAL: [
        {
            "filename": "gk_rf_supply.txt",
            "content": """
Гражданский кодекс РФ - Глава 30. Купля-продажа
Параграф 3. Поставка товаров

Статья 506. Договор поставки
По договору поставки поставщик-продавец обязуется передать в обусловленный срок товары покупателю для использования в предпринимательской деятельности.

Статья 509. Срок поставки товаров
Поставка товаров осуществляется в сроки, установленные договором.

Статья 516. Оплата товаров
Покупатель оплачивает поставляемые товары с соблюдением порядка и формы расчетов, предусмотренных договором.
"""
        }
    ]
}


def initialize_knowledge_base():
    """Инициализировать базу знаний с примерами"""
    kb_manager = KnowledgeBaseManager()

    # Добавить примеры документов
    for category, documents in SAMPLE_DOCUMENTS.items():
        for doc in documents:
            try:
                kb_manager.add_document(
                    category,
                    doc["filename"],
                    doc["content"]
                )
            except Exception as e:
                logger.error(f"Error adding document: {e}")

    return kb_manager
