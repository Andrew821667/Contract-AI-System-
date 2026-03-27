# -*- coding: utf-8 -*-
"""
Graph-RAG Evaluation Set

Gold-вопросы для оценки качества Graph-RAG vs Flat-RAG.

Каждый вопрос содержит:
- question: текст вопроса
- category: тип вопроса (exact, analytical, cross_reference, entity, structural)
- expected: эталонные данные для проверки
  - answer_contains: ключевые фрагменты, которые должны быть в контексте
  - source_number: номер пункта-источника
  - confidence: ожидаемый уровень уверенности
  - entities: ожидаемые сущности
- graph_advantage: почему Graph-RAG лучше flat RAG для этого вопроса

Тестовый документ: tests/fixtures/test_supply_contract.txt
"""

# ──────────────────────────────────────────────
# Тестовый текст НПА (ст. 330 ГК РФ)
# ──────────────────────────────────────────────

TEST_NPA_TEXT = """
ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ
ЧАСТЬ ПЕРВАЯ

Раздел III. ОБЩАЯ ЧАСТЬ ОБЯЗАТЕЛЬСТВЕННОГО ПРАВА

Глава 23. Обеспечение исполнения обязательств

§ 2. Неустойка

Статья 330. Понятие неустойки
1. Неустойкой (штрафом, пеней) признается определенная законом или договором денежная
сумма, которую должник обязан уплатить кредитору в случае неисполнения или ненадлежащего
исполнения обязательства, в частности в случае просрочки исполнения.
2. По требованию об уплате неустойки кредитор не обязан доказывать причинение ему убытков.
3. Кредитор не вправе требовать уплаты неустойки, если должник не несет ответственности
за неисполнение или ненадлежащее исполнение обязательства.

Статья 331. Форма соглашения о неустойке
1. Соглашение о неустойке должно быть совершено в письменной форме независимо от формы
основного обязательства.
2. Несоблюдение письменной формы влечет недействительность соглашения о неустойке.

Статья 332. Законная неустойка
1. Кредитор вправе требовать уплаты неустойки, определенной законом (законной неустойки),
независимо от того, предусмотрена ли обязанность ее уплаты соглашением сторон.
2. Размер законной неустойки может быть увеличен соглашением сторон, если закон этого
не запрещает.

Статья 333. Уменьшение неустойки
Если подлежащая уплате неустойка явно несоразмерна последствиям нарушения обязательства,
суд вправе уменьшить неустойку.

Глава 30. Купля-продажа

§ 3. Поставка товаров

Статья 506. Договор поставки
По договору поставки поставщик-продавец, осуществляющий предпринимательскую деятельность,
обязуется передать в обусловленный срок или сроки производимые или закупаемые им товары
покупателю для использования в предпринимательской деятельности.

Статья 521. Неустойка за недопоставку или просрочку поставки товаров
1. Установленная законом или договором поставки неустойка за недопоставку или просрочку
поставки товаров взыскивается с поставщика до фактического исполнения обязательства в
пределах его обязанности восполнить недопоставленное количество товаров в последующих
периодах поставки, если иной порядок уплаты неустойки не установлен законом или договором.
"""


# ──────────────────────────────────────────────
# Gold-вопросы
# ──────────────────────────────────────────────

EVALUATION_QUESTIONS = [
    # ──── Категория: EXACT (прямой ответ в конкретном пункте) ────

    {
        "id": "Q01",
        "question": "Какова общая стоимость договора?",
        "category": "exact",
        "expected": {
            "answer_contains": ["1 500 000", "рублей"],
            "source_number": "2.1",
            "confidence": "high",
            "entities": [{"type": "monetary", "amount": 1500000.0}],
        },
        "graph_advantage": "Exact match по пункту 2.1 + entity extraction (monetary)",
    },
    {
        "id": "Q02",
        "question": "Какой размер предоплаты по договору?",
        "category": "exact",
        "expected": {
            "answer_contains": ["30%", "450 000"],
            "source_number": "2.3",
            "confidence": "high",
            "entities": [{"type": "monetary", "amount": 450000.0}],
        },
        "graph_advantage": "Точная навигация к п. 2.3 + extraction суммы",
    },
    {
        "id": "Q03",
        "question": "Каков срок поставки товара?",
        "category": "exact",
        "expected": {
            "answer_contains": ["15 февраля 2024"],
            "source_number": "3.1",
            "confidence": "high",
            "entities": [{"type": "date_ref", "date_type": "deadline"}],
        },
        "graph_advantage": "Exact match п. 3.1 + date entity с типом deadline",
    },
    {
        "id": "Q04",
        "question": "Какой размер неустойки за нарушение сроков поставки?",
        "category": "exact",
        "expected": {
            "answer_contains": ["0,1%", "не более 10%"],
            "source_number": "5.1",
            "confidence": "high",
        },
        "graph_advantage": "Exact match п. 5.1 + clause_type: penalty",
    },
    {
        "id": "Q05",
        "question": "Куда доставляется товар?",
        "category": "exact",
        "expected": {
            "answer_contains": ["ул. Промышленная", "д. 25"],
            "source_number": "3.2",
            "confidence": "high",
        },
        "graph_advantage": "Exact match п. 3.2",
    },

    # ──── Категория: STRUCTURAL (требует навигации по дереву) ────

    {
        "id": "Q06",
        "question": "Какие обязанности у Поставщика?",
        "category": "structural",
        "expected": {
            "answer_contains": ["надлежащего качества", "сохранность", "документы"],
            "source_number": "4.1",
            "confidence": "high",
            "expected_children": ["4.1.1", "4.1.2", "4.1.3"],
        },
        "graph_advantage": "Graph traversal: п.4.1 → дочерние 4.1.1, 4.1.2, 4.1.3. "
                           "Flat RAG может пропустить подпункты или вернуть их разрозненно.",
    },
    {
        "id": "Q07",
        "question": "Какие разделы содержит договор?",
        "category": "structural",
        "expected": {
            "answer_contains": ["ПРЕДМЕТ", "ЦЕНА", "ПОСТАВКИ", "ОТВЕТСТВЕННОСТЬ"],
            "confidence": "high",
            "expected_sections": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        },
        "graph_advantage": "Дерево: все section-узлы уровня 0. Flat RAG не знает структуру.",
    },
    {
        "id": "Q08",
        "question": "Что написано в разделе про форс-мажор?",
        "category": "structural",
        "expected": {
            "answer_contains": ["непреодолимой силы", "освобождаются от ответственности"],
            "source_number": "6.1",
            "confidence": "high",
        },
        "graph_advantage": "Навигация по section title → children",
    },

    # ──── Категория: ENTITY (поиск по извлечённым сущностям) ────

    {
        "id": "Q09",
        "question": "Какие денежные суммы упомянуты в договоре?",
        "category": "entity",
        "expected": {
            "entities": [
                {"type": "monetary", "amount": 1500000.0},
                {"type": "monetary", "amount": 250000.0},
                {"type": "monetary", "amount": 450000.0},
                {"type": "monetary", "amount": 1050000.0},
            ],
            "confidence": "high",
        },
        "graph_advantage": "Entity search по type=monetary. Flat RAG вернёт случайные чанки.",
    },
    {
        "id": "Q10",
        "question": "Какие даты упомянуты в договоре?",
        "category": "entity",
        "expected": {
            "entities": [
                {"type": "date_ref", "value": "2024-01-15"},
                {"type": "date_ref", "value": "2024-02-15"},
                {"type": "date_ref", "value": "2024-03-31"},
            ],
            "confidence": "high",
        },
        "graph_advantage": "Entity search по type=date_ref с date_type аннотацией.",
    },

    # ──── Категория: CROSS_REFERENCE (ссылки между пунктами / на НПА) ────

    {
        "id": "Q11",
        "question": "На какие приложения ссылается договор?",
        "category": "cross_reference",
        "expected": {
            "answer_contains": ["Приложение № 1", "Спецификац"],
            "source_number": "1.1",
            "confidence": "high",
        },
        "graph_advantage": "Fact edge: appendix_ref из п. 1.1 → Приложение 1",
    },
    {
        "id": "Q12",
        "question": "Где указаны реквизиты для оплаты?",
        "category": "cross_reference",
        "expected": {
            "answer_contains": ["разделе 10", "расчетный счет"],
            "source_number": "2.4",
            "confidence": "high",
        },
        "graph_advantage": "Fact edge: clause_ref из п. 2.4 → раздел 10. "
                           "Graph даёт оба пункта; flat RAG — только один.",
    },

    # ──── Категория: ANALYTICAL (вопросы требующие интерпретации) ────

    {
        "id": "Q13",
        "question": "Насколько справедлив размер неустойки в договоре?",
        "category": "analytical",
        "expected": {
            "answer_contains": ["0,1%", "не более 10%"],
            "source_number": "5.1",
            "confidence": "medium",
        },
        "graph_advantage": "Graph-RAG: п.5.1 + п.5.2 (симметричность) + ст.333 ГК (уменьшение). "
                           "Flat RAG: только один чанк без cross-layer контекста.",
    },
    {
        "id": "Q14",
        "question": "Каковы риски для Покупателя по этому договору?",
        "category": "analytical",
        "expected": {
            "answer_contains": ["предоплата", "30%", "сроки"],
            "confidence": "medium",
        },
        "graph_advantage": "Structural traversal по всем разделам + entity extraction (суммы, сроки)",
    },

    # ──── Категория: CROSS_LAYER (договор + НПА) ────

    {
        "id": "Q15",
        "question": "Как соотносится неустойка в договоре со ст. 330 ГК РФ?",
        "category": "cross_layer",
        "expected": {
            "answer_contains": ["0,1%", "договорная неустойка", "ст. 330"],
            "confidence": "medium",
        },
        "graph_advantage": "Cross-layer: п.5.1 договора → ст.330 ГК (через norm_ref entity). "
                           "Graph-RAG отдаёт контекст обоих слоёв. Flat RAG не связывает.",
    },
    {
        "id": "Q16",
        "question": "Соответствует ли порядок неустойки требованиям ст. 331 ГК РФ?",
        "category": "cross_layer",
        "expected": {
            "answer_contains": ["письменной форме", "ст. 331"],
            "confidence": "medium",
        },
        "graph_advantage": "Graph-RAG: ст.331 ГК (требование письменной формы) + п.5 договора "
                           "(неустойка прописана в договоре = письменная форма). "
                           "Flat RAG не знает о связи.",
    },
    {
        "id": "Q17",
        "question": "Что говорит ГК РФ о неустойке за просрочку поставки?",
        "category": "cross_layer",
        "expected": {
            "answer_contains": ["ст. 521", "до фактического исполнения"],
            "confidence": "high",
        },
        "graph_advantage": "Поиск в NPA слое по ст. 521 + cross-ref на п.5.1 договора",
    },

    # ──── Категория: NO_DATA (ответа в документах нет) ────

    {
        "id": "Q18",
        "question": "Какие сертификаты качества предоставил Поставщик?",
        "category": "no_data",
        "expected": {
            "answer_contains": [],
            "confidence": "low",
        },
        "graph_advantage": "Graph-RAG корректно определит confidence=low: п.4.1.3 упоминает "
                           "сертификаты как обязанность, но самих сертификатов в документе нет.",
    },
    {
        "id": "Q19",
        "question": "Каковы условия страхования груза?",
        "category": "no_data",
        "expected": {
            "answer_contains": [],
            "confidence": "no_data",
        },
        "graph_advantage": "Нет пункта о страховании. Graph-RAG: confidence=no_data. "
                           "Flat RAG может выдать нерелевантный чанк.",
    },

    # ──── Категория: MULTI_HOP (ответ собирается из нескольких пунктов) ────

    {
        "id": "Q20",
        "question": "Каков порядок оплаты и какие последствия за просрочку?",
        "category": "multi_hop",
        "expected": {
            "answer_contains": ["предоплата", "30%", "70%", "0,1%", "не более 10%"],
            "source_numbers": ["2.3", "5.2"],
            "confidence": "high",
        },
        "graph_advantage": "Graph: п.2.3 (порядок оплаты) + п.5.2 (неустойка за просрочку оплаты). "
                           "Fact edge: clause_ref может связать эти пункты. "
                           "Flat RAG выдаст один чанк, не оба.",
    },
    {
        "id": "Q21",
        "question": "До какой даты действует договор и можно ли его расторгнуть досрочно?",
        "category": "multi_hop",
        "expected": {
            "answer_contains": ["31 марта 2024", "по соглашению", "одностороннем порядке", "30"],
            "source_numbers": ["8.1", "8.2"],
            "confidence": "high",
        },
        "graph_advantage": "Graph: section 8 → п.8.1 (срок) + п.8.2 (расторжение). "
                           "Structural expansion раздела.",
    },
    {
        "id": "Q22",
        "question": "Какие документы Поставщик должен передать Покупателю и как происходит приёмка?",
        "category": "multi_hop",
        "expected": {
            "answer_contains": ["сертификаты", "паспорта качества", "Акт приема-передачи"],
            "source_numbers": ["4.1.3", "3.3"],
            "confidence": "high",
        },
        "graph_advantage": "Graph: п.4.1.3 (документы) + п.3.3 (приёмка). "
                           "Связь через structural traversal + keyword overlap.",
    },

    # ──── Категория: COMPARISON (сравнение пунктов) ────

    {
        "id": "Q23",
        "question": "Одинаковы ли условия неустойки для Поставщика и Покупателя?",
        "category": "comparison",
        "expected": {
            "answer_contains": ["0,1%", "не более 10%", "симметрич"],
            "source_numbers": ["5.1", "5.2"],
            "confidence": "high",
        },
        "graph_advantage": "Graph: п.5.1 (Поставщик) vs п.5.2 (Покупатель) — sibling nodes. "
                           "Entity extraction: оба 0.1%, cap 10%. "
                           "Flat RAG вернёт один пункт.",
    },
]


# ──────────────────────────────────────────────
# Метрики для evaluation
# ──────────────────────────────────────────────

def evaluate_retrieval(
    retrieved_nodes: list,
    expected: dict,
) -> dict:
    """
    Оценка качества retrieval для одного вопроса.

    Returns:
        {
            hit: bool — найден ли ожидаемый пункт,
            answer_coverage: float — доля найденных ключевых фрагментов (0-1),
            confidence_match: bool — совпадает ли уровень уверенности,
            entity_recall: float — доля найденных сущностей (0-1),
        }
    """
    result = {
        "hit": False,
        "answer_coverage": 0.0,
        "confidence_match": False,
        "entity_recall": 0.0,
    }

    # Hit: найден ли ожидаемый пункт
    expected_number = expected.get("source_number")
    if expected_number:
        for node in retrieved_nodes:
            number = getattr(node, 'number', None) if hasattr(node, 'number') else node.get('number')
            if number == expected_number:
                result["hit"] = True
                break

    # Answer coverage: доля ключевых фрагментов в контексте
    answer_contains = expected.get("answer_contains", [])
    if answer_contains:
        all_text = " ".join(
            (getattr(n, 'text', '') if hasattr(n, 'text') else n.get('text', ''))
            for n in retrieved_nodes
        ).lower()
        found = sum(1 for frag in answer_contains if frag.lower() in all_text)
        result["answer_coverage"] = found / len(answer_contains)

    return result


def run_evaluation_summary(results: list) -> dict:
    """
    Сводка по всем вопросам evaluation set.

    Args:
        results: Список {question_id, hit, answer_coverage, ...}

    Returns:
        {total, hit_rate, avg_coverage, by_category: {...}}
    """
    total = len(results)
    hits = sum(1 for r in results if r.get("hit"))
    avg_coverage = sum(r.get("answer_coverage", 0) for r in results) / total if total else 0

    # По категориям
    by_category = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"total": 0, "hits": 0, "coverage_sum": 0}
        by_category[cat]["total"] += 1
        if r.get("hit"):
            by_category[cat]["hits"] += 1
        by_category[cat]["coverage_sum"] += r.get("answer_coverage", 0)

    for cat, data in by_category.items():
        data["hit_rate"] = data["hits"] / data["total"] if data["total"] else 0
        data["avg_coverage"] = data["coverage_sum"] / data["total"] if data["total"] else 0
        del data["coverage_sum"]

    return {
        "total_questions": total,
        "hit_rate": hits / total if total else 0,
        "avg_answer_coverage": avg_coverage,
        "by_category": by_category,
    }
