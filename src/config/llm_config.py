"""
LLM Configuration for Multi-Model Routing
Supports: DeepSeek-V3, Claude 4.5 Sonnet, GPT-4o, GPT-4o-mini

DEPRECATED: This config duplicates settings from config/settings.py.
New code should use `from config.settings import settings` for LLM configuration.
This module is kept for backward compatibility with model_router.py.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Tuple
from functools import lru_cache


class LLMConfig(BaseSettings):
    """
    Configuration for all supported LLM models.

    Models:
    - DeepSeek-V3: Primary worker ($0.14/1M tokens) - 90% задач
    - Claude 4.5 Sonnet: Expert fallback ($3.00/1M tokens) - сложные сканы
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
        default="deepseek-v3",
        description="DeepSeek model name"
    )
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
        default="deepseek-v3",
        description="Default model for Smart Router"
    )
    ROUTER_COMPLEXITY_THRESHOLD: float = Field(
        default=0.8,
        description="Complexity threshold for switching to Claude (0.0-1.0)"
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

    # Costs per 1M tokens (input) — March 2026
    COST_DEEPSEEK_INPUT: float = Field(default=0.28, description="DeepSeek V3.2 cost per 1M input tokens")
    COST_CLAUDE_INPUT: float = Field(default=3.00, description="Claude Sonnet 4.6 cost per 1M input tokens")
    COST_GPT_INPUT: float = Field(default=2.50, description="GPT-5.4 cost per 1M input tokens")
    COST_GPT_MINI_INPUT: float = Field(default=0.75, description="GPT-5.4 Mini cost per 1M input tokens")
    COST_GEMINI_FLASH_INPUT: float = Field(default=0.30, description="Gemini 2.5 Flash cost per 1M input tokens")
    COST_GEMINI_PRO_INPUT: float = Field(default=1.25, description="Gemini 2.5 Pro cost per 1M input tokens")

    # Costs per 1M tokens (output) — March 2026
    COST_DEEPSEEK_OUTPUT: float = Field(default=0.42, description="DeepSeek V3.2 cost per 1M output tokens")
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
        if model in (self.DEEPSEEK_MODEL, "deepseek-chat", "deepseek-v3", "deepseek-v3.2"):
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
            self.DEEPSEEK_MODEL,
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
            model: Model name (deepseek-chat, claude-sonnet-4-6-20250227, gpt-5.4, gpt-5.4-mini)

        Returns:
            Tuple of (input_cost, output_cost) per 1M tokens
        """
        costs = {
            "deepseek-chat": (self.COST_DEEPSEEK_INPUT, self.COST_DEEPSEEK_OUTPUT),
            "deepseek-v3.2": (self.COST_DEEPSEEK_INPUT, self.COST_DEEPSEEK_OUTPUT),
            "claude-sonnet-4-6-20250227": (self.COST_CLAUDE_INPUT, self.COST_CLAUDE_OUTPUT),
            "claude-haiku-4-5-20251001": (1.00, 5.00),
            "gpt-5.4": (self.COST_GPT_INPUT, self.COST_GPT_OUTPUT),
            "gpt-5.4-mini": (self.COST_GPT_MINI_INPUT, self.COST_GPT_MINI_OUTPUT),
            "gemini-2.5-flash": (self.COST_GEMINI_FLASH_INPUT, self.COST_GEMINI_FLASH_OUTPUT),
            "gemini-2.5-pro": (self.COST_GEMINI_PRO_INPUT, self.COST_GEMINI_PRO_OUTPUT),
            self.OLLAMA_MODEL: (0.0, 0.0),  # Локальная модель — бесплатно
        }
        return costs.get(model, (0.0, 0.0))

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
    cost = config.calculate_cost("deepseek-v3", tokens_input=1000, tokens_output=500)
    print(f"Cost for 1000 input + 500 output tokens (DeepSeek): ${cost:.6f}")
