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
from datetime import datetime, timezone
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

    def __init__(self, fns_api_key: Optional[str] = None, use_dadata: bool = False):
        """
        Initialize counterparty service

        Args:
            fns_api_key: Optional API key for Dadata.ru (premium FNS data)
            use_dadata: Use Dadata.ru API if api_key provided
        """
        # Initialize FNS API client
        from .fns_api import FNSAPIClient
        self.fns_client = FNSAPIClient(api_key=fns_api_key, use_dadata=use_dadata)

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
            'checked_at': datetime.now(timezone.utc).isoformat(),
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

        Uses FNS API client with fallback to stub data
        """
        logger.info(f"Checking FNS for INN: {inn}")

        try:
            # Validate INN format first
            validation = self.fns_client.check_inn_format(inn)
            if not validation['valid']:
                logger.warning(f"Invalid INN format: {inn} - {validation['errors']}")
                return {
                    'found': False,
                    'inn': inn,
                    'error': f"Invalid INN: {', '.join(validation['errors'])}",
                    'data_source': 'Validation'
                }

            # Get company info from FNS
            company_info = self.fns_client.get_company_info(inn)

            # Normalize response format
            if company_info.get('found'):
                name_data = company_info.get('name', {})
                result = {
                    'found': True,
                    'inn': inn,
                    'name': name_data.get('full') or name_data.get('short', f'Компания {inn}'),
                    'short_name': name_data.get('short'),
                    'ogrn': company_info.get('ogrn'),
                    'kpp': company_info.get('kpp'),
                    'registration_date': company_info.get('registration_date'),
                    'active': company_info.get('active', False),
                    'status': company_info.get('status', 'UNKNOWN'),
                    'legal_address': company_info.get('legal_address'),
                    'ceo': company_info.get('ceo'),
                    'authorized_capital': company_info.get('authorized_capital'),
                    'opf': company_info.get('opf'),  # Org form
                    'okved': company_info.get('okved'),  # Activity type
                    'data_source': company_info.get('data_source', 'FNS API')
                }
                logger.info(f"✓ FNS: Found {result['name']}")
            else:
                result = {
                    'found': False,
                    'inn': inn,
                    'error': company_info.get('error', 'Not found'),
                    'data_source': company_info.get('data_source', 'FNS API')
                }
                logger.warning(f"✗ FNS: Company not found for INN {inn}")

            return result

        except Exception as e:
            logger.error(f"FNS API error: {e}")
            # Return error result
            return {
                'found': False,
                'inn': inn,
                'error': str(e),
                'data_source': 'FNS API (error)'
            }

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
            # Note: Fedresurs public API is free but has rate limits
            response = requests.get(
                f"{self.fedresurs_api_url}",
                params={'inn': inn},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('pageData'):
                    result['has_bankruptcy_cases'] = True
                    result['cases'] = data['pageData']
                    logger.info(f"Fedresurs: Found {len(data['pageData'])} bankruptcy cases for {inn}")
                else:
                    logger.info(f"Fedresurs: No bankruptcy cases for {inn}")
            else:
                logger.warning(f"Fedresurs API returned status {response.status_code}")
                result['has_bankruptcy_cases'] = False

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

    def get_or_create_by_inn(
        self,
        db,
        inn: str,
        organization_id: Optional[str],
        created_by: Optional[str],
        fns_check_result: Optional[Dict[str, Any]] = None,
    ):
        """
        Найти контрагента по (organization_id, inn) или создать с обогащением через ФНС.

        Args:
            db: SQLAlchemy session
            inn: ИНН контрагента
            organization_id: ID организации-тенанта (None для legacy)
            created_by: ID пользователя-создателя
            fns_check_result: Готовый результат self.check_counterparty(inn) — чтобы
                              не дёргать API повторно. Если None — будет вызов.

        Returns:
            Counterparty | None — None если ФНС не нашла компанию.
        """
        from src.models.counterparty_models import Counterparty

        existing = (
            db.query(Counterparty)
            .filter(
                Counterparty.organization_id == organization_id,
                Counterparty.inn == inn,
            )
            .first()
        )

        check = fns_check_result if fns_check_result is not None else self.check_counterparty(inn)
        fns = check.get("fns_data", {}) or {}
        bankruptcy = check.get("bankruptcy_data", {}) or {}
        now = datetime.now(timezone.utc)

        if existing:
            existing.fns_data = fns
            existing.fns_checked_at = now
            if bankruptcy:
                existing.bankruptcy_data = bankruptcy
                existing.bankruptcy_checked_at = now
            db.commit()
            db.refresh(existing)
            return existing

        if not fns.get("found"):
            return None

        cp = Counterparty(
            organization_id=organization_id,
            created_by=created_by,
            type="legal",
            status="active",
            name=fns.get("name") or f"Компания {inn}",
            short_name=fns.get("short_name"),
            inn=inn,
            kpp=fns.get("kpp"),
            ogrn=fns.get("ogrn"),
            legal_address=fns.get("legal_address"),
            fns_data=fns,
            fns_checked_at=now,
            bankruptcy_data=bankruptcy or None,
            bankruptcy_checked_at=now if bankruptcy else None,
        )
        db.add(cp)
        db.commit()
        db.refresh(cp)
        logger.info(f"Counterparty created via lookup: id={cp.id} inn={inn}")
        return cp

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
            'checked_at': datetime.now(timezone.utc).isoformat()
        }


__all__ = ["CounterpartyService"]
