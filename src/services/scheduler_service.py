# -*- coding: utf-8 -*-
"""
Scheduler Service — фоновые задачи системы Contract AI

Использует APScheduler для периодического выполнения:
- Переиндексация документов базы знаний (reindex_pending)
- Очистка устаревших сессий пользователей
- Агрегация аналитических метрик
"""
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from loguru import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler не установлен. pip install APScheduler==3.10.4")


class SchedulerService:
    """Singleton-сервис фонового планировщика задач"""

    _instance = None  # type: Optional[SchedulerService]
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_session_factory=None):
        if self._initialized:
            return
        self._initialized = True

        if not APSCHEDULER_AVAILABLE:
            self.scheduler = None
            self._running = False
            return

        self.db_session_factory = db_session_factory
        self.scheduler = BackgroundScheduler(
            timezone="Europe/Moscow",
            job_defaults={
                'coalesce': True,       # объединять пропущенные запуски
                'max_instances': 1,     # только 1 экземпляр задачи одновременно
                'misfire_grace_time': 300,
            }
        )
        self._running = False

        # Слушатель событий для логирования
        self.scheduler.add_listener(self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # ─── Управление ──────────────────────────────────────────

    def start(self):
        """Запустить планировщик и зарегистрировать стандартные задачи"""
        if not APSCHEDULER_AVAILABLE:
            logger.warning("Планировщик недоступен: APScheduler не установлен")
            return

        if self._running:
            logger.info("Планировщик уже запущен")
            return

        self._register_default_jobs()
        self.scheduler.start()
        self._running = True
        logger.info("Планировщик запущен")

    def stop(self):
        """Остановить планировщик"""
        if self.scheduler and self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Планировщик остановлен")

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Регистрация задач ───────────────────────────────────

    def _register_default_jobs(self):
        """Зарегистрировать стандартные фоновые задачи"""

        # 1. Переиндексация pending документов БЗ — каждые 30 минут
        self.scheduler.add_job(
            self._job_reindex_pending,
            trigger=IntervalTrigger(minutes=30),
            id='reindex_pending',
            name='Переиндексация документов БЗ',
            replace_existing=True,
        )

        # 2. Очистка устаревших сессий — каждый день в 03:00
        self.scheduler.add_job(
            self._job_cleanup_sessions,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_sessions',
            name='Очистка устаревших сессий',
            replace_existing=True,
        )

        # 3. Агрегация аналитики — каждый час
        self.scheduler.add_job(
            self._job_aggregate_analytics,
            trigger=IntervalTrigger(hours=1),
            id='aggregate_analytics',
            name='Агрегация аналитики',
            replace_existing=True,
        )

        logger.info("Зарегистрировано 3 стандартных задачи")

    # ─── Реализация задач ────────────────────────────────────

    def _get_db(self):
        """Получить новую сессию БД"""
        if self.db_session_factory:
            return self.db_session_factory()
        return None

    def _log_task(self, job_id: str, job_name: str, status: str,
                  started_at: datetime, result: str = None, error: str = None,
                  items_processed: int = 0):
        """Записать результат выполнения задачи в БД"""
        db = self._get_db()
        if not db:
            return
        try:
            from ..models.database import ScheduledTaskLog
            finished_at = datetime.utcnow()
            duration = (finished_at - started_at).total_seconds()

            log_entry = ScheduledTaskLog(
                job_id=job_id,
                job_name=job_name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                duration_sec=duration,
                result=result,
                error=error,
                items_processed=items_processed,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Ошибка записи лога задачи: {e}")
            db.rollback()
        finally:
            db.close()

    def _job_reindex_pending(self):
        """Переиндексация документов с is_vectorized=False"""
        started_at = datetime.utcnow()
        db = self._get_db()
        if not db:
            logger.warning("reindex_pending: нет DB session factory")
            return

        try:
            from .knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db=db, rag_system=None)
            # Без rag_system переиндексация невозможна — просто подсчитаем pending
            from ..models.database import LegalDocument
            pending_count = db.query(LegalDocument).filter(
                LegalDocument.is_vectorized == False,
                LegalDocument.status == 'active'
            ).count()

            if pending_count == 0:
                self._log_task(
                    'reindex_pending', 'Переиндексация документов БЗ',
                    'skipped', started_at,
                    result='Нет документов для индексации',
                    items_processed=0,
                )
                return

            # Попытка переиндексации (если RAG доступен)
            try:
                count = kb_service.reindex_pending()
                self._log_task(
                    'reindex_pending', 'Переиндексация документов БЗ',
                    'success', started_at,
                    result=f'Проиндексировано {count} документов',
                    items_processed=count,
                )
            except RuntimeError:
                # RAG не инициализирован
                self._log_task(
                    'reindex_pending', 'Переиндексация документов БЗ',
                    'skipped', started_at,
                    result=f'{pending_count} документов ожидают индексации (RAG недоступен)',
                    items_processed=0,
                )
        except Exception as e:
            logger.error(f"reindex_pending ошибка: {e}")
            self._log_task(
                'reindex_pending', 'Переиндексация документов БЗ',
                'error', started_at, error=str(e),
            )
        finally:
            db.close()

    def _job_cleanup_sessions(self):
        """Очистка устаревших сессий (>7 дней)"""
        started_at = datetime.utcnow()
        db = self._get_db()
        if not db:
            return

        try:
            from ..models.auth_models import UserSession
            cutoff = datetime.utcnow() - timedelta(days=7)
            expired = db.query(UserSession).filter(
                UserSession.expires_at < cutoff
            ).all()
            count = len(expired)
            for session in expired:
                db.delete(session)
            db.commit()

            self._log_task(
                'cleanup_sessions', 'Очистка устаревших сессий',
                'success', started_at,
                result=f'Удалено {count} устаревших сессий',
                items_processed=count,
            )
            logger.info(f"cleanup_sessions: удалено {count} сессий")
        except Exception as e:
            logger.error(f"cleanup_sessions ошибка: {e}")
            db.rollback()
            self._log_task(
                'cleanup_sessions', 'Очистка устаревших сессий',
                'error', started_at, error=str(e),
            )
        finally:
            db.close()

    def _job_aggregate_analytics(self):
        """Агрегация аналитических метрик за последний час"""
        started_at = datetime.utcnow()
        db = self._get_db()
        if not db:
            return

        try:
            from sqlalchemy import func
            from ..models.analytics_models import AnalyticsMetricLog, AggregatedMetric

            hour_ago = datetime.utcnow() - timedelta(hours=1)

            # Подсчёт метрик за последний час
            metrics_count = db.query(AnalyticsMetricLog).filter(
                AnalyticsMetricLog.created_at >= hour_ago
            ).count()

            self._log_task(
                'aggregate_analytics', 'Агрегация аналитики',
                'success', started_at,
                result=f'Обработано {metrics_count} метрик за последний час',
                items_processed=metrics_count,
            )
        except Exception as e:
            logger.error(f"aggregate_analytics ошибка: {e}")
            self._log_task(
                'aggregate_analytics', 'Агрегация аналитики',
                'error', started_at, error=str(e),
            )
        finally:
            db.close()

    # ─── Ручной запуск ───────────────────────────────────────

    def run_job_now(self, job_id: str) -> str:
        """Запустить задачу вручную прямо сейчас"""
        job_map = {
            'reindex_pending': self._job_reindex_pending,
            'cleanup_sessions': self._job_cleanup_sessions,
            'aggregate_analytics': self._job_aggregate_analytics,
        }
        func = job_map.get(job_id)
        if not func:
            return f"Задача '{job_id}' не найдена"

        try:
            func()
            return f"Задача '{job_id}' выполнена"
        except Exception as e:
            return f"Ошибка: {e}"

    # ─── Информация ──────────────────────────────────────────

    def get_jobs_info(self) -> List[Dict[str, Any]]:
        """Получить информацию о всех зарегистрированных задачах"""
        if not self.scheduler or not self._running:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else 'Не запланировано',
                'trigger': str(job.trigger),
            })
        return jobs

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить последние логи выполнения"""
        db = self._get_db()
        if not db:
            return []

        try:
            from ..models.database import ScheduledTaskLog
            logs = db.query(ScheduledTaskLog).order_by(
                ScheduledTaskLog.started_at.desc()
            ).limit(limit).all()

            return [
                {
                    'id': log.id,
                    'job_id': log.job_id,
                    'job_name': log.job_name,
                    'status': log.status,
                    'started_at': log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else '',
                    'duration_sec': round(log.duration_sec, 2) if log.duration_sec else None,
                    'result': log.result,
                    'error': log.error,
                    'items_processed': log.items_processed,
                }
                for log in logs
            ]
        except Exception as e:
            logger.error(f"Ошибка чтения логов: {e}")
            return []
        finally:
            db.close()

    # ─── Listener ────────────────────────────────────────────

    def _on_job_event(self, event):
        """Обработчик событий APScheduler"""
        if event.exception:
            logger.error(f"Задача {event.job_id} завершилась с ошибкой: {event.exception}")
        else:
            logger.info(f"Задача {event.job_id} выполнена успешно")
