# -*- coding: utf-8 -*-
from src.models.analyzer_models import ContractRisk
from src.services.recommendation_generator import RecommendationGenerator
from src.services.risk_analyzer import RiskAnalyzer
from src.utils.analysis_filters import (
    should_ignore_future_date_risk,
    should_ignore_required_field,
    should_ignore_signatory_authority_risk,
)


class _DummyLLM:
    def call(self, *args, **kwargs):
        return {"recommendations": []}


def test_signature_placeholders_are_not_required_fields():
    assert should_ignore_required_field({
        'title': '7. РЕКВИЗИТЫ И ПОДПИСИ СТОРОН',
        'description': 'В договоре есть незаполненное место.',
        'snippet': 'Ген. директор __________(Иванов И.И.)',
    })
    assert not should_ignore_required_field({
        'title': 'Банковские реквизиты',
        'description': 'Не указан корреспондентский счет.',
        'snippet': 'БИК 044525974, к/с __________',
    })


def test_fallback_recommendations_created_from_required_fields_and_risks():
    generator = RecommendationGenerator(_DummyLLM())
    risk = ContractRisk(
        risk_type='financial',
        severity='high',
        probability='medium',
        title='Неопределенные сроки и условия оплаты',
        description='Срок оплаты не согласован.',
        consequences='Поставщик рискует не получить оплату вовремя.',
        section_name='4. Порядок расчетов',
    )

    recommendations = generator.generate_recommendations(
        [risk],
        rag_context={},
        required_fields=[
            {
                'title': 'Спецификация к договору',
                'description': 'Нужно определить предмет поставки.',
                'snippet': 'Товар определяется в спецификации',
            }
        ],
    )

    titles = [item.title for item in recommendations]

    assert any(title.startswith('Запросить у пользователя данные: Спецификация к договору') for title in titles)
    assert any('оплат' in title.lower() or 'расчет' in title.lower() for title in titles)


def test_required_fields_can_force_user_input_recommendation():
    generator = RecommendationGenerator(_DummyLLM())

    recommendations = generator.generate_recommendations(
        [],
        rag_context={},
        required_fields=[
            {
                'title': 'Предмет договора',
                'description': 'Система не должна придумывать предмет договора.',
                'snippet': 'Поставщик обязуется поставить __________',
                'needs_user_input': True,
                'user_question': 'Что именно поставляется, в каком количестве и с какими характеристиками?',
                'missing_data_points': ['наименование товара', 'количество', 'характеристики'],
            }
        ],
    )

    assert recommendations
    assert recommendations[0].title.startswith('Запросить у пользователя данные:')
    assert 'не должна подставлять' in (recommendations[0].description or '').lower()
    assert 'какие именно поставляется' not in (recommendations[0].description or '').lower()
    assert 'наименование товара' in (recommendations[0].description or '').lower()


def test_future_date_risk_ignored_when_date_is_not_future():
    text = (
        'Недействительность договора из-за даты в будущем. '
        'Договор датирован 30 марта 2026 года, что якобы является будущей датой '
        'относительно текущей даты анализа (2026-04-02).'
    )

    assert should_ignore_future_date_risk(text, '2026-04-02')


def test_generic_signatory_authority_check_is_ignored():
    text = (
        'Риск оспаривания полномочий подписанта. Указано, что генеральный директор '
        'действует на основании Устава. Не представлена выписка из ЕГРЮЛ или доверенность, '
        'подтверждающая полномочия на момент подписания.'
    )

    assert should_ignore_signatory_authority_risk(text)


def test_batch_prompt_includes_contract_context_and_user_input_rules():
    analyzer = RiskAnalyzer(_DummyLLM())
    prompt = analyzer._build_batch_analysis_prompt(
        clauses=[
            {
                'id': '1',
                'type': 'subject',
                'title': 'Предмет договора',
                'text': 'Поставщик обязуется поставить товар в ассортименте согласно спецификации.',
            }
        ],
        rag_context={
            'contract_summary': {
                'type': 'договор поставки',
                'subject': 'поставка зерна',
                'parties': [
                    {'name': 'ООО Поставщик', 'role': 'поставщик'},
                    {'name': 'ООО Покупатель', 'role': 'покупатель'},
                ],
            }
        },
        analysis_context={
            'analysis_date': '2026-04-02',
            'analysis_perspective': 'Поставщик',
        },
    )

    assert 'Тип договора: договор поставки' in prompt
    assert 'Предмет договора: поставка зерна' in prompt
    assert 'ООО Поставщик (поставщик)' in prompt
    assert 'не выдумывай значения' in prompt
    assert 'нужно запросить у пользователя' in prompt
    assert 'предметом договора' in prompt.lower()
