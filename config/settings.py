"""
Конфигурация приложения Contract AI System
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database
    # По умолчанию SQLite, можно переключить на PostgreSQL в .env
    database_url: str = "sqlite:///./contract_ai.db"

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    gigachat_api_key: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    deepseek_api_key: str = ""
    qwen_api_key: str = ""

    # Default LLM Provider
    default_llm_provider: Literal["claude", "openai", "perplexity", "yandex", "gigachat", "deepseek", "qwen"] = "openai"

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

    # Streamlit
    streamlit_server_port: int = 8501
    streamlit_server_address: str = "localhost"

    # Redis (optional)
    redis_url: str = "redis://localhost:6379/0"

    # LLM Settings
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4000
    llm_timeout: int = 120

    # RAG Settings
    rag_top_k: int = 5
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Security
    secret_key: str = "your-secret-key-here"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
