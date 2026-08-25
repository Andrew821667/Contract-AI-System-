"""Regression tests for the DeepSeek Flash/Pro routing policy."""

from types import SimpleNamespace

from src.core.llm_models import (
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_PRO_MODEL,
    normalize_model_name,
    normalize_reasoning_model_name,
    normalize_standard_model_name,
    openai_compatible_client_options,
    openai_compatible_model_options,
)


def test_legacy_deepseek_names_are_normalized() -> None:
    assert normalize_model_name("deepseek-chat") == DEEPSEEK_FLASH_MODEL
    assert normalize_model_name("deepseek-v3") == DEEPSEEK_FLASH_MODEL
    assert normalize_model_name("deepseek-reasoner") == DEEPSEEK_PRO_MODEL


def test_legacy_environment_values_follow_field_purpose() -> None:
    assert normalize_standard_model_name("deepseek-reasoner") == DEEPSEEK_FLASH_MODEL
    assert normalize_reasoning_model_name("deepseek-chat") == DEEPSEEK_PRO_MODEL


def test_legacy_config_values_are_migrated_by_field_role() -> None:
    from src.config.llm_config import LLMConfig

    config = LLMConfig(
        DEEPSEEK_MODEL="deepseek-reasoner",
        DEEPSEEK_REASONING_MODEL="deepseek-chat",
        ROUTER_DEFAULT_MODEL="deepseek-v3",
        _env_file=None,
    )

    assert config.DEEPSEEK_MODEL == DEEPSEEK_FLASH_MODEL
    assert config.DEEPSEEK_REASONING_MODEL == DEEPSEEK_PRO_MODEL
    assert config.ROUTER_DEFAULT_MODEL == DEEPSEEK_FLASH_MODEL


def test_flash_explicitly_disables_thinking() -> None:
    options = openai_compatible_model_options(DEEPSEEK_FLASH_MODEL)

    assert options == {
        "model": DEEPSEEK_FLASH_MODEL,
        "extra_body": {"thinking": {"type": "disabled"}},
    }


def test_pro_enables_high_effort_thinking() -> None:
    options = openai_compatible_model_options(DEEPSEEK_PRO_MODEL)

    assert options["model"] == DEEPSEEK_PRO_MODEL
    assert options["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }


def test_deepseek_client_uses_deepseek_endpoint() -> None:
    options = openai_compatible_client_options(
        DEEPSEEK_FLASH_MODEL,
        api_key="test-key",
    )

    assert options == {
        "api_key": "test-key",
        "base_url": "https://api.deepseek.com/v1",
    }


class _FakeCompletions:
    def __init__(self) -> None:
        self.params = None

    def create(self, **kwargs):
        self.params = kwargs
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )


def _gateway_for(model: str):
    from src.services.llm_gateway import LLMGateway

    gateway = object.__new__(LLMGateway)
    gateway.provider = "deepseek"
    gateway.model = normalize_model_name(model)
    gateway.total_input_tokens = 0
    gateway.total_output_tokens = 0
    completions = _FakeCompletions()
    gateway._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    return gateway, completions


def test_gateway_sends_flash_without_thinking() -> None:
    gateway, completions = _gateway_for("deepseek-chat")

    result = gateway._call_openai_compatible("hello", None, 0.2, 100)

    assert result == "ok"
    assert gateway.model == DEEPSEEK_FLASH_MODEL
    assert completions.params["model"] == DEEPSEEK_FLASH_MODEL
    assert completions.params["temperature"] == 0.2
    assert completions.params["extra_body"] == {
        "thinking": {"type": "disabled"},
    }


def test_implicit_gateway_ignores_a_stale_openai_default() -> None:
    from config.settings import settings
    from src.services.llm_gateway import LLMGateway

    original_provider = settings.default_llm_provider
    original_key = settings.deepseek_api_key
    settings.default_llm_provider = "openai"
    settings.deepseek_api_key = ""
    try:
        gateway = LLMGateway()
    finally:
        settings.default_llm_provider = original_provider
        settings.deepseek_api_key = original_key

    assert gateway.provider == "deepseek"
    assert gateway.model == DEEPSEEK_FLASH_MODEL


def test_gateway_sends_pro_with_reasoning_and_without_temperature() -> None:
    gateway, completions = _gateway_for("deepseek-reasoner")

    result = gateway._call_openai_compatible("hello", None, 0.2, 100)

    assert result == "ok"
    assert gateway.model == DEEPSEEK_PRO_MODEL
    assert completions.params["model"] == DEEPSEEK_PRO_MODEL
    assert "temperature" not in completions.params
    assert completions.params["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }


def test_standard_cascade_does_not_include_pro() -> None:
    from src.core.llm_cascade.cascade_manager import CASCADE_LEVELS

    for level in ("orchestration", "agent"):
        assert DEEPSEEK_FLASH_MODEL == CASCADE_LEVELS[level]["preferred_models"][0]
        assert DEEPSEEK_PRO_MODEL not in CASCADE_LEVELS[level]["preferred_models"]

    assert DEEPSEEK_PRO_MODEL == CASCADE_LEVELS["expert"]["preferred_models"][0]


def test_router_uses_pro_only_for_serious_work() -> None:
    from src.services.model_router import ModelRouter

    router = ModelRouter()
    router.config.ROUTER_COMPLEXITY_THRESHOLD = 0.8

    assert router.select_model(doc_complexity_score=0.5) == DEEPSEEK_FLASH_MODEL
    assert router.select_model(doc_complexity_score=0.9) == DEEPSEEK_PRO_MODEL
    assert router.select_model(user_mode="expert") == DEEPSEEK_PRO_MODEL


def test_cascade_level_respects_the_expert_threshold() -> None:
    from src.services.model_router import _v1_to_cascade_level

    assert _v1_to_cascade_level(0.79, True, "optimal", 0.8) == "agent"
    assert _v1_to_cascade_level(0.8, False, "optimal", 0.8) == "expert"
    assert _v1_to_cascade_level(0.1, False, "expert", 0.8) == "expert"


def test_standard_fallback_chain_does_not_add_pro() -> None:
    from src.core.llm_cascade.cascade_manager import CascadeManager
    from src.core.llm_cascade.routing_policy import LLMRoutingPolicy

    class _RoutingPolicyService:
        @staticmethod
        def get_policy(**_kwargs):
            return LLMRoutingPolicy()

        @staticmethod
        def apply_policy(model, **_kwargs):
            return model, "test policy"

    manager = CascadeManager(_RoutingPolicyService(), object())

    standard = manager.select_model_for_level("agent")
    expert = manager.select_model_for_level("expert")

    assert standard["model"] == DEEPSEEK_FLASH_MODEL
    assert DEEPSEEK_PRO_MODEL not in standard["fallback_chain"]
    assert expert["model"] == DEEPSEEK_PRO_MODEL


def test_legacy_cloud_model_is_not_treated_as_local() -> None:
    from src.core.llm_cascade.routing_policy import LLMRoutingPolicy

    policy = LLMRoutingPolicy(local_models=["deepseek-v3"])

    assert policy.local_models == ["qwen3:7b"]


def test_policy_normalizes_models_by_route_role() -> None:
    from src.core.llm_cascade.routing_policy import LLMRoutingPolicy

    policy = LLMRoutingPolicy(
        default_model="deepseek-reasoner",
        high_sensitivity_model="deepseek-chat",
    )

    assert policy.default_model == DEEPSEEK_FLASH_MODEL
    assert policy.high_sensitivity_model == DEEPSEEK_PRO_MODEL


def test_system_router_keeps_legacy_reasoner_on_standard_route() -> None:
    import asyncio
    from src.services.system_config_service import SystemConfigService

    service = SystemConfigService(db_session=object())

    async def _legacy_config(_key: str):
        return {"default_model": "deepseek-reasoner", "complexity_threshold": 0.8}

    service._get_config = _legacy_config
    config = asyncio.run(service.get_router_config())

    assert config["default_model"] == DEEPSEEK_FLASH_MODEL
