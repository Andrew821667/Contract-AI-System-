# -*- coding: utf-8 -*-
"""
Counterparty Service - Check counterparty information via APIs

Integrations:
- FNS API (free, basic info)
- Fedresurs API (free, bankruptcy info)
- SPARK, Kontur.Focus (stubs for future paid integrations)
"""
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger


class CounterpartyService:
    """
    Service for checking counterparty information

    Free APIs:
    - FNS (Federal Tax Service) - basic company info
    - Fedresurs - bankruptcy information

    Paid APIs (stubs):
    - SPARK-Interfax
    - Kontur.Focus
    """

    def __init__(self):
        # API endpoints
        self.fns_api_url = "https://egrul.nalog.ru"
        self.fedresurs_api_url = "https://fedresurs.ru/backend/companies"

        # Paid APIs (stubs)
        self.spark_api_url = None  # Requires subscription
        self.kontur_api_url = None  # Requires subscription

    def check_counterparty(
        self,
        inn: str,
        check_bankruptcy: bool = True,
        check_paid_sources: bool = False
    ) -> Dict[str, Any]:
        """
        Check counterparty by INN

        Args:
            inn: INN (ИНН) of the counterparty
            check_bankruptcy: Check bankruptcy status
            check_paid_sources: Use paid APIs (SPARK, Kontur)

        Returns:
            Dictionary with counterparty information
        """
        logger.info(f"Checking counterparty: INN {inn}")

        result = {
            'inn': inn,
            'checked_at': datetime.utcnow().isoformat(),
            'fns_data': {},
            'bankruptcy_data': {},
            'paid_sources_data': {},
            'overall_status': 'unknown',
            'warnings': [],
            'errors': []
        }

        # 1. Check FNS (basic info)
        try:
            fns_data = self._check_fns(inn)
            result['fns_data'] = fns_data

            if not fns_data.get('found'):
                result['warnings'].append('Компания не найдена в ЕГРЮЛ')
                result['overall_status'] = 'not_found'
                return result

        except Exception as e:
            logger.error(f"FNS check failed: {e}")
            result['errors'].append(f'FNS API error: {str(e)}')

        # 2. Check bankruptcy status
        if check_bankruptcy:
            try:
                bankruptcy_data = self._check_fedresurs(inn)
                result['bankruptcy_data'] = bankruptcy_data

                if bankruptcy_data.get('has_bankruptcy_cases'):
                    result['warnings'].append('Найдены дела о банкротстве')
                    result['overall_status'] = 'risky'

            except Exception as e:
                logger.error(f"Fedresurs check failed: {e}")
                result['errors'].append(f'Fedresurs API error: {str(e)}')

        # 3. Check paid sources (if enabled)
        if check_paid_sources:
            try:
                paid_data = self._check_paid_sources(inn)
                result['paid_sources_data'] = paid_data
            except Exception as e:
                logger.error(f"Paid sources check failed: {e}")
                result['errors'].append(f'Paid sources error: {str(e)}')

        # Determine overall status
        if result['overall_status'] == 'unknown':
            if result['fns_data'].get('active') and not result['bankruptcy_data'].get('has_bankruptcy_cases'):
                result['overall_status'] = 'ok'
            elif not result['fns_data'].get('active'):
                result['overall_status'] = 'inactive'
                result['warnings'].append('Компания неактивна')

        logger.info(f"Counterparty check complete: {result['overall_status']}")
        return result

    def _check_fns(self, inn: str) -> Dict[str, Any]:
        """
        Check FNS (Federal Tax Service) API

        Note: Real FNS API requires special access.
        This is a simplified stub implementation.
        """
        logger.info(f"Checking FNS for INN: {inn}")

        # TODO: Implement real FNS API integration
        # For now, return stub data

        # Stub implementation
        result = {
            'found': True,
            'inn': inn,
            'name': f'ООО "Компания {inn}"',
            'ogrn': '1234567890123',
            'registration_date': '2020-01-15',
            'active': True,
            'legal_address': 'г. Москва, ул. Примерная, д. 1',
            'ceo': 'Иванов И.И.',
            'authorized_capital': 10000,
            'data_source': 'FNS API (stub)'
        }

        # In real implementation, would make API request:
        # response = requests.get(f"{self.fns_api_url}/search", params={'inn': inn})
        # result = response.json()

        return result

    def _check_fedresurs(self, inn: str) -> Dict[str, Any]:
        """
        Check Fedresurs (bankruptcy registry)

        Fedresurs provides open API for bankruptcy information
        """
        logger.info(f"Checking Fedresurs for INN: {inn}")

        result = {
            'checked': True,
            'inn': inn,
            'has_bankruptcy_cases': False,
            'cases': [],
            'data_source': 'Fedresurs API'
        }

        try:
            # Real Fedresurs API call
            # Note: Fedresurs API might require authentication or have rate limits

            # Stub implementation - in production would call real API:
            # response = requests.get(
            #     f"{self.fedresurs_api_url}",
            #     params={'inn': inn},
            #     timeout=10
            # )
            # if response.status_code == 200:
            #     data = response.json()
            #     if data.get('pageData'):
            #         result['has_bankruptcy_cases'] = True
            #         result['cases'] = data['pageData']

            # For now, return stub (no bankruptcy cases)
            result['has_bankruptcy_cases'] = False
            result['data_source'] = 'Fedresurs API (stub)'

        except requests.RequestException as e:
            logger.warning(f"Fedresurs API request failed: {e}")
            result['error'] = str(e)

        return result

    def _check_paid_sources(self, inn: str) -> Dict[str, Any]:
        """
        Check paid sources: SPARK-Interfax, Kontur.Focus

        These are stubs for future integration
        """
        logger.info(f"Checking paid sources for INN: {inn}")

        result = {
            'spark': self._check_spark_stub(inn),
            'kontur_focus': self._check_kontur_stub(inn)
        }

        return result

    def _check_spark_stub(self, inn: str) -> Dict[str, Any]:
        """
        SPARK-Interfax API stub

        To integrate: https://spark-interfax.ru/api
        Requires: API key and paid subscription
        """
        return {
            'available': False,
            'message': 'SPARK API integration not configured. Requires paid subscription.',
            'endpoint': 'https://spark-interfax.ru/api',
            'documentation': 'https://spark-interfax.ru/api/docs'
        }

    def _check_kontur_stub(self, inn: str) -> Dict[str, Any]:
        """
        Kontur.Focus API stub

        To integrate: https://focus.kontur.ru/api
        Requires: API key and paid subscription
        """
        return {
            'available': False,
            'message': 'Kontur.Focus API integration not configured. Requires paid subscription.',
            'endpoint': 'https://focus-api.kontur.ru',
            'documentation': 'https://focus.kontur.ru/api/docs'
        }

    def check_multiple(self, inn_list: list) -> Dict[str, Dict[str, Any]]:
        """
        Check multiple counterparties

        Args:
            inn_list: List of INNs

        Returns:
            Dictionary with INN as key and check results as value
        """
        logger.info(f"Checking {len(inn_list)} counterparties")

        results = {}
        for inn in inn_list:
            try:
                results[inn] = self.check_counterparty(inn)
            except Exception as e:
                logger.error(f"Failed to check INN {inn}: {e}")
                results[inn] = {
                    'inn': inn,
                    'overall_status': 'error',
                    'errors': [str(e)]
                }

        return results

    def get_risk_assessment(self, counterparty_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risk based on counterparty data

        Args:
            counterparty_data: Result from check_counterparty

        Returns:
            Risk assessment
        """
        risk_level = 'low'
        risk_factors = []

        # Check status
        if counterparty_data['overall_status'] == 'not_found':
            risk_level = 'critical'
            risk_factors.append('Компания не найдена в ЕГРЮЛ')

        elif counterparty_data['overall_status'] == 'inactive':
            risk_level = 'high'
            risk_factors.append('Компания неактивна')

        elif counterparty_data['overall_status'] == 'risky':
            risk_level = 'high'
            risk_factors.extend(counterparty_data.get('warnings', []))

        # Check bankruptcy
        if counterparty_data.get('bankruptcy_data', {}).get('has_bankruptcy_cases'):
            risk_level = 'critical'
            risk_factors.append('Обнаружены дела о банкротстве')

        # Check authorized capital (if too low)
        fns_data = counterparty_data.get('fns_data', {})
        capital = fns_data.get('authorized_capital', 0)
        if capital < 10000:
            if risk_level == 'low':
                risk_level = 'medium'
            risk_factors.append(f'Низкий уставный капитал: {capital} руб.')

        return {
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'checked_at': datetime.utcnow().isoformat()
        }


__all__ = ["CounterpartyService"]
