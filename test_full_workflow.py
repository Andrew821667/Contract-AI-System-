#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест полного workflow - анализ тестового договора
"""
from pathlib import Path
from config.settings import settings
from src.models import init_db, SessionLocal
from src.services.llm_gateway import LLMGateway
from src.services.document_parser import DocumentParser
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent

print("=" * 70)
print("ТЕСТИРОВАНИЕ ПОЛНОГО WORKFLOW: АНАЛИЗ ДОГОВОРА")
print("=" * 70)
print()

# 1. Инициализация
print("1. Инициализация компонентов...")
init_db()
db = SessionLocal()
llm_gateway = LLMGateway(provider="openai")
parser = DocumentParser()
print("   ✓ Все компоненты инициализированы")
print()

# 2. Парсинг тестового договора
print("2. Парсинг тестового договора...")
test_file = Path("tests/fixtures/test_contract.docx")

if not test_file.exists():
    print(f"   ❌ Тестовый файл не найден: {test_file}")
    exit(1)

parsed_xml = parser.parse(str(test_file))
print(f"   ✓ Договор распарсен ({len(parsed_xml)} символов XML)")
print()

# 3. Создание записи в БД
print("3. Создание записи договора в БД...")
from src.models import Contract
from datetime import datetime

import json
contract = Contract(
    file_name=test_file.name,
    file_path=str(test_file),
    document_type="contract",
    contract_type="supply",
    status="analyzing",
    meta_info=json.dumps({"test": True})
)
db.add(contract)
db.commit()
db.refresh(contract)
print(f"   ✓ Договор создан с ID: {contract.id}")
print()

# 4. Анализ с помощью Contract Analyzer Agent
print("4. Запуск Contract Analyzer Agent...")
print("   (Это может занять 10-30 секунд, идёт запрос к OpenAI...)")
print()

try:
    analyzer = ContractAnalyzerAgent(
        llm_gateway=llm_gateway,
        db_session=db
    )

    result = analyzer.execute({
        'contract_id': contract.id,
        'parsed_xml': parsed_xml,
        'metadata': {
            'file_name': test_file.name,
            'contract_type': 'supply'
        }
    })

    if result.success:
        print("   ✅ АНАЛИЗ ЗАВЕРШЁН УСПЕШНО!")
        print()
        print("=" * 70)
        print("РЕЗУЛЬТАТЫ АНАЛИЗА:")
        print("=" * 70)

        data = result.data

        # Риски
        if 'risks' in data and data['risks']:
            print(f"\n📊 ВЫЯВЛЕНО РИСКОВ: {len(data['risks'])}")
            for i, risk in enumerate(data['risks'][:3], 1):  # Показываем первые 3
                print(f"\n{i}. {risk.get('title', 'Риск')}")
                print(f"   Категория: {risk.get('category', 'N/A')}")
                print(f"   Серьёзность: {risk.get('severity', 'N/A')}")
                print(f"   Описание: {risk.get('description', 'N/A')[:100]}...")

        # Рекомендации
        if 'recommendations' in data and data['recommendations']:
            print(f"\n\n💡 РЕКОМЕНДАЦИИ: {len(data['recommendations'])}")
            for i, rec in enumerate(data['recommendations'][:3], 1):
                print(f"\n{i}. {rec.get('title', 'Рекомендация')}")
                print(f"   Приоритет: {rec.get('priority', 'N/A')}")
                print(f"   Описание: {rec.get('description', 'N/A')[:100]}...")

        # Общая оценка
        if 'overall_risk_level' in data:
            print(f"\n\n⚠️  ОБЩИЙ УРОВЕНЬ РИСКА: {data['overall_risk_level']}")

        print("\n" + "=" * 70)
        print("✅ ПОЛНЫЙ WORKFLOW ПРОТЕСТИРОВАН УСПЕШНО!")
        print("=" * 70)

    else:
        print(f"   ❌ Ошибка анализа: {result.error}")

except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
