"""
LLM Configuration for Multi-Model Routing
Supports: DeepSeek V4 Flash/Pro, Claude, GPT and local models

DEPRECATED: This config duplicates settings from config/settings.py.
New code should use `from config.settings import settings` for LLM configuration.
This module is kept for backward compatibility with model_router.py.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, Tuple
from functools import lru_cache

from src.core.llm_models import (
    DEEPSEEK_FLASH_INPUT_COST,
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_FLASH_OUTPUT_COST,
    DEEPSEEK_PRO_INPUT_COST,
    DEEPSEEK_PRO_MODEL,
    DEEPSEEK_PRO_OUTPUT_COST,
    is_deepseek_model,
    normalize_model_name,
    normalize_reasoning_model_name,
    normalize_standard_model_name,
)


class LLMConfig(BaseSettings):
    """
    Configuration for all supported LLM models.

    Models:
    - DeepSeek V4 Flash: primary worker without thinking
    - DeepSeek V4 Pro: serious/expert tasks with thinking
    - Claude Sonnet: expert fallback
    - GPT-4o: Reserve channel ($2.50/1M tokens)
    - GPT-4o-mini: Testing/validation ($0.15/1M tokens)
    """

    # ========================================
    # DeepSeek Configuration
    # ========================================
    DEEPSEEK_API_KEY: str = Field(default="", description="DeepSeek API key")
    DEEPSEEK_BASE_URL: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL"
    )
    DEEPSEEK_MODEL: str = Field(
        default=DEEPSEEK_FLASH_MODEL,
        description="DeepSeek model for standard tasks"
    )
    DEEPSEEK_REASONING_MODEL: str = Field(
        default=DEEPSEEK_PRO_MODEL,
        description="DeepSeek reasoning model for serious tasks"
    )

    @field_validator("DEEPSEEK_MODEL", "ROUTER_DEFAULT_MODEL", check_fields=False)
    @classmethod
    def normalize_standard_model(cls, model: str) -> str:
        return normalize_standard_model_name(model)

    @field_validator("DEEPSEEK_REASONING_MODEL")
    @classmethod
    def normalize_reasoning_model(cls, model: str) -> str:
        return normalize_reasoning_model_name(model)
    DEEPSEEK_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for DeepSeek responses"
    )
    DEEPSEEK_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for DeepSeek (lower = more deterministic)"
    )

    # ========================================
    # Anthropic Claude Configuration
    # ========================================
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    ANTHROPIC_MODEL: str = Field(
        default="claude-sonnet-4-6-20250227",
        description="Claude model name"
    )
    ANTHROPIC_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for Claude responses"
    )
    ANTHROPIC_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for Claude"
    )

    # ========================================
    # OpenAI Configuration
    # ========================================
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_MODEL: str = Field(
        default="gpt-5.4",
        description="GPT-5.4 flagship model"
    )
    OPENAI_MODEL_MINI: str = Field(
        default="gpt-5.4-mini",
        description="GPT-5.4 Mini model for budget tasks"
    )
    OPENAI_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for GPT-4o responses"
    )
    OPENAI_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for GPT-4o"
    )

    # ========================================
    # Ollama (Local LLM) Configuration
    # ========================================
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    OLLAMA_MODEL: str = Field(
        default="qwen3:7b",
        description="Default Ollama model"
    )
    OLLAMA_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for Ollama responses"
    )
    OLLAMA_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for Ollama"
    )

    # ========================================
    # Smart Router Configuration
    # ========================================
    ROUTER_DEFAULT_MODEL: str = Field(
        default=DEEPSEEK_FLASH_MODEL,
        description="Default model for Smart Router"
    )
    ROUTER_COMPLEXITY_THRESHOLD: float = Field(
        default=0.8,
        description="Complexity threshold for switching to DeepSeek Pro (0.0-1.0)"
    )
    ROUTER_ENABLE_FALLBACK: bool = Field(
        default=True,
        description="Enable fallback to alternative models on failure"
    )

    # ========================================
    # RAG Configuration
    # ========================================
    RAG_ENABLED: bool = Field(
        default=True,
        description="Enable RAG (Retrieval-Augmented Generation)"
    )
    RAG_TOP_K: int = Field(
        default=5,
        description="Number of documents to retrieve for RAG context"
    )
    RAG_SIMILARITY_THRESHOLD: float = Field(
        default=0.7,
        description="Minimum similarity score for RAG retrieval (0.0-1.0)"
    )

    # ========================================
    # Retry and Timeout Configuration
    # ========================================
    REQUEST_TIMEOUT: int = Field(
        default=120,
        description="Request timeout in seconds"
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries on API failure"
    )
    RETRY_DELAY: float = Field(
        default=1.0,
        description="Initial delay between retries (exponential backoff)"
    )

    # ========================================
    # Cost Tracking
    # ========================================
    COST_TRACKING_ENABLED: bool = Field(
        default=True,
        description="Enable cost tracking for LLM usage"
    )

    # Costs per 1M tokens (input)
    COST_DEEPSEEK_INPUT: float = Field(default=DEEPSEEK_FLASH_INPUT_COST, description="DeepSeek Flash cost per 1M input tokens")
    COST_DEEPSEEK_PRO_INPUT: float = Field(default=DEEPSEEK_PRO_INPUT_COST, description="DeepSeek Pro cost per 1M input tokens")
    COST_CLAUDE_INPUT: float = Field(default=3.00, description="Claude Sonnet 4.6 cost per 1M input tokens")
    COST_GPT_INPUT: float = Field(default=2.50, description="GPT-5.4 cost per 1M input tokens")
    COST_GPT_MINI_INPUT: float = Field(default=0.75, description="GPT-5.4 Mini cost per 1M input tokens")
    COST_GEMINI_FLASH_INPUT: float = Field(default=0.30, description="Gemini 2.5 Flash cost per 1M input tokens")
    COST_GEMINI_PRO_INPUT: float = Field(default=1.25, description="Gemini 2.5 Pro cost per 1M input tokens")

    # Costs per 1M tokens (output)
    COST_DEEPSEEK_OUTPUT: float = Field(default=DEEPSEEK_FLASH_OUTPUT_COST, description="DeepSeek Flash cost per 1M output tokens")
    COST_DEEPSEEK_PRO_OUTPUT: float = Field(default=DEEPSEEK_PRO_OUTPUT_COST, description="DeepSeek Pro cost per 1M output tokens")
    COST_CLAUDE_OUTPUT: float = Field(default=15.00, description="Claude Sonnet 4.6 cost per 1M output tokens")
    COST_GPT_OUTPUT: float = Field(default=20.00, description="GPT-5.4 cost per 1M output tokens")
    COST_GPT_MINI_OUTPUT: float = Field(default=4.50, description="GPT-5.4 Mini cost per 1M output tokens")
    COST_GEMINI_FLASH_OUTPUT: float = Field(default=2.50, description="Gemini 2.5 Flash cost per 1M output tokens")
    COST_GEMINI_PRO_OUTPUT: float = Field(default=10.00, description="Gemini 2.5 Pro cost per 1M output tokens")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def get_model_credentials(self, model: str) -> Tuple[str, Optional[str]]:
        """
        Get API key and base_url for a given model.

        Returns:
            Tuple of (api_key, base_url). base_url is None for OpenAI/Anthropic.
        """
        model = normalize_model_name(model)
        if is_deepseek_model(model):
            return self.DEEPSEEK_API_KEY, self.DEEPSEEK_BASE_URL
        elif "claude" in model:
            return self.ANTHROPIC_API_KEY, None
        elif "gpt-" in model or "o3" in model:
            return self.OPENAI_API_KEY, None
        elif "gemini" in model:
            return self.GOOGLE_API_KEY if hasattr(self, 'GOOGLE_API_KEY') else "", None
        elif model == self.OLLAMA_MODEL or model.startswith("qwen") or model.startswith("llama") or model.startswith("mistral") or model.startswith("gemma") or model.startswith("deepseek-v3.2-exp"):
            return "ollama", f"{self.OLLAMA_BASE_URL}/v1"
        else:
            # Default to DeepSeek
            return self.DEEPSEEK_API_KEY, self.DEEPSEEK_BASE_URL

    def is_model_available(self, model: str) -> bool:
        """Check if a model has a valid API key configured."""
        api_key, _ = self.get_model_credentials(model)
        if api_key == "ollama":
            return True  # Ollama не требует API ключа
        return bool(api_key) and not api_key.startswith("your_")

    def get_available_models(self):
        """Return list of models with valid API keys."""
        all_models = [
            normalize_model_name(self.DEEPSEEK_MODEL),
            normalize_model_name(self.DEEPSEEK_REASONING_MODEL, DEEPSEEK_PRO_MODEL),
            self.ANTHROPIC_MODEL,
            "claude-haiku-4-5-20251001",
            self.OPENAI_MODEL,
            self.OPENAI_MODEL_MINI,
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            self.OLLAMA_MODEL,
        ]
        return [m for m in all_models if self.is_model_available(m)]

    def get_model_costs(self, model: str) -> Tuple[float, float]:
        """
        Get input and output costs per 1M tokens for a given model.

        Args:
            model: Model name

        Returns:
            Tuple of (input_cost, output_cost) per 1M tokens
        """
        normalized = normalize_model_name(model)
        if normalized == DEEPSEEK_FLASH_MODEL:
            return self.COST_DEEPSEEK_INPUT, self.COST_DEEPSEEK_OUTPUT
        if normalized == DEEPSEEK_PRO_MODEL:
            return self.COST_DEEPSEEK_PRO_INPUT, self.COST_DEEPSEEK_PRO_OUTPUT

        costs = {
            "claude-sonnet-4-6-20250227": (self.COST_CLAUDE_INPUT, self.COST_CLAUDE_OUTPUT),
            "claude-haiku-4-5-20251001": (1.00, 5.00),
            "gpt-5.4": (self.COST_GPT_INPUT, self.COST_GPT_OUTPUT),
            "gpt-5.4-mini": (self.COST_GPT_MINI_INPUT, self.COST_GPT_MINI_OUTPUT),
            "gemini-2.5-flash": (self.COST_GEMINI_FLASH_INPUT, self.COST_GEMINI_FLASH_OUTPUT),
            "gemini-2.5-pro": (self.COST_GEMINI_PRO_INPUT, self.COST_GEMINI_PRO_OUTPUT),
            self.OLLAMA_MODEL: (0.0, 0.0),  # Локальная модель — бесплатно
        }
        return costs.get(normalized, (0.0, 0.0))

    def calculate_cost(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int
    ) -> float:
        """
        Calculate total cost for a given model and token usage.

        Args:
            model: Model name
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens

        Returns:
            Total cost in USD
        """
        cost_input, cost_output = self.get_model_costs(model)
        total_cost = (
            (tokens_input / 1_000_000) * cost_input +
            (tokens_output / 1_000_000) * cost_output
        )
        return round(total_cost, 6)


@lru_cache()
def get_llm_config() -> LLMConfig:
    """
    Get cached LLM configuration instance.

    Returns:
        LLMConfig instance
    """
    return LLMConfig()


# Example usage:
if __name__ == "__main__":
    config = get_llm_config()
    print(f"Default model: {config.ROUTER_DEFAULT_MODEL}")
    print(f"RAG enabled: {config.RAG_ENABLED}")

    # Calculate cost example
    cost = config.calculate_cost(DEEPSEEK_FLASH_MODEL, tokens_input=1000, tokens_output=500)
    print(f"Cost for 1000 input + 500 output tokens (DeepSeek): ${cost:.6f}")
