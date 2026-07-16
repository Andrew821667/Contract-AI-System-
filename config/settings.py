"""
Конфигурация приложения Contract AI System
"""
import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database — PostgreSQL only
    # Local dev: docker compose -f docker-compose.dev.yml up -d
    database_url: str = "postgresql://contract_user:dev_password@localhost:5432/contract_ai"

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    deepseek_api_key: str = ""

    # RAG feature flags
    rag_rewrite: bool = False   # RAG_REWRITE=1 → query rewriting via deepseek-chat
    rag_graph_hop: bool = False  # RAG_GRAPH_HOP=1 → multi-hop обогащение связанными нормами (граф)
    qwen_api_key: str = ""

    # Google Gemini
    google_api_key: str = ""

    # Ollama (Local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:7b"

    # Default LLM Provider
    default_llm_provider: Literal["claude", "openai", "perplexity", "yandex", "deepseek", "qwen", "ollama", "google"] = "deepseek"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"

    # File Storage
    upload_dir: str = "./data/uploads"
    normalized_dir: str = "./data/normalized"
    reports_dir: str = "./data/reports"
    templates_dir: str = "./data/templates"
    exports_dir: str = "./data/exports"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    debug: bool = False  # Will be set automatically based on app_env in __init__

    # Streamlit
    streamlit_server_port: int = 8501
    streamlit_server_address: str = "localhost"

    # Redis (optional)
    redis_url: str = "redis://localhost:6379/0"

    # Bridge Integration (Legal AI Platform)
    bridge_secret: str = ""  # Shared secret для bridge API и SSO

    # LLM Settings
    llm_temperature: float = 0.0
    llm_max_tokens: int = 16000  # Увеличено для полнотекстового анализа
    llm_timeout: int = 180  # Увеличено: full-text анализ может занять больше времени
    llm_retry_attempts: int = 3

    # Local LLM safety rails (Ollama and similar slow self-hosted providers)
    llm_local_timeout: int = 45
    llm_local_retry_attempts: int = 1
    llm_local_full_text_analysis: bool = False
    llm_local_batch_size: int = 3
    llm_local_max_concurrent_batches: int = 1

    # Full-text analysis — отправка всего текста договора в LLM
    full_text_analysis: bool = True  # True = двухпроходный (full-text + clause-level), False = только clause-level

    # Test Mode - экономия токенов
    llm_test_mode: bool = False  # Переключатель: True = тестовый режим, False = продакшн

    # Two-level analysis system
    llm_quick_model: str = "deepseek-chat"  # Быстрый анализ (Уровень 1)
    llm_deep_model: str = "deepseek-chat"   # Глубокий анализ (Уровень 2)

    # Batch analysis settings
    llm_batch_size: int = 10  # Пунктов в одном батче (уменьшено — клаузулы теперь полные)
    max_concurrent_batches: int = 3  # Макс. параллельных батчей при анализе

    # Token limits for test mode
    llm_test_max_tokens: int = 800       # Для тестового режима
    llm_test_max_clauses: int = 20       # Макс. пунктов для анализа в тесте (увеличено для эффективности)

    # Model pricing (per 1M tokens) для расчёта стоимости — актуально на март 2026
    llm_pricing: dict = {
        "deepseek-chat": {"input": 0.28, "output": 0.42},
        "claude-sonnet-4-6-20250227": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
        "gpt-5.4": {"input": 2.50, "output": 20.00},
        "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "qwen3:7b": {"input": 0.0, "output": 0.0},
    }

    # RAG Settings
    rag_top_k: int = 5
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Security — REQUIRED! Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    secret_key: str = ""
    # Separate key for HMAC document signatures (isolate from JWT secret)
    document_signing_key: str = ""

    # Email / SMTP Settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Contract AI System"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Security validation: require SECRET_KEY in production
        if self.app_env == "production" and not self.secret_key:
            raise ValueError(
                "❌ SECRET_KEY must be set in production environment!\n"
                "Generate a secure key with:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
                "Then add to .env file:\n"
                "  SECRET_KEY=<generated-key>"
            )

        # Auto-generate SECRET_KEY in dev if not set (with loud warning).
        # ВАЖНО: ключ ДЕТЕРМИНИРОВАННЫЙ (sha256 от пути проекта), а не random.
        # Раньше каждый gunicorn-воркер генерил СВОЙ random-ключ (+ гонка записи
        # .env) → JWT валиден только на «своём» воркере → плавающие 401. Детермин.
        # ключ одинаков во всех воркерах без координации и переживает рестарты.
        if self.secret_key in ["", "your-secret-key-here", "changeme", "secret"]:
            if self.app_env in ("development", "testing"):
                import hashlib as _hashlib
                import warnings
                _proj = os.path.dirname(os.path.dirname(__file__))
                generated_key = _hashlib.sha256(
                    f"contract-ai-dev-secret::{_proj}".encode()
                ).hexdigest()
                self.secret_key = generated_key
                # Persist to .env so the same key survives restarts
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
                try:
                    if os.path.exists(env_path):
                        with open(env_path, "r") as f:
                            env_content = f.read()
                        if "SECRET_KEY=" in env_content:
                            import re as _re
                            env_content = _re.sub(
                                r"^SECRET_KEY=.*$", f"SECRET_KEY={generated_key}", env_content, flags=_re.MULTILINE
                            )
                        else:
                            env_content += f"\nSECRET_KEY={generated_key}\n"
                        with open(env_path, "w") as f:
                            f.write(env_content)
                except OSError:
                    pass
                warnings.warn(
                    "⚠️  SECRET_KEY not set! Auto-generated and saved to .env.\n"
                    f"  SECRET_KEY={generated_key}",
                    UserWarning,
                    stacklevel=2
                )
            else:
                import warnings
                warnings.warn(
                    "⚠️  Using empty or default SECRET_KEY! This is INSECURE!\n"
                    f"Current environment: {self.app_env}",
                    UserWarning,
                    stacklevel=2
                )

        # Auto-generate DOCUMENT_SIGNING_KEY if not set (separate from JWT secret)
        if not self.document_signing_key:
            if self.app_env in ("development", "testing"):
                import secrets
                self.document_signing_key = secrets.token_urlsafe(32)
            else:
                import warnings
                warnings.warn(
                    "⚠️  DOCUMENT_SIGNING_KEY not set! Document HMAC signatures will be insecure.\n"
                    "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
                    UserWarning,
                    stacklevel=2
                )

        # Auto-set debug based on environment (must be explicitly enabled via DEBUG env var)
        if os.environ.get("DEBUG"):
            self.debug = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
        else:
            self.debug = False  # Never auto-enable debug — must be explicit

        # Security: never allow debug in production
        if self.app_env == "production" and self.debug:
            import warnings
            warnings.warn(
                "DEBUG=true is forbidden in production! Forcing debug=False.",
                UserWarning,
                stacklevel=2
            )
            self.debug = False

        # Создаём необходимые директории
        self._create_directories()

    def _create_directories(self):
        """Создаёт необходимые директории для хранения файлов"""
        directories = [
            self.upload_dir,
            self.normalized_dir,
            self.reports_dir,
            self.templates_dir,
            self.exports_dir,
            self.chroma_persist_directory
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()


# Экспорт для удобного импорта
__all__ = ["settings", "Settings"]
