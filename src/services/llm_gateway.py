"""
LLM Gateway - 48=0O B>G:0 4>ABC?0 :> 2A5< LLM ?@>20945@0<
>445@6:0: Claude, GPT-4, Perplexity, YandexGPT, GigaChat, DeepSeek, Qwen
"""
import json
import hashlib
from typing import Dict, Any, Literal, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from config.settings import settings


class LLMGateway:
    """Unified gateway for all LLM providers"""

    def __init__(self, provider: Optional[str] = None):
        """
        =8F80;870F8O gateway

        Args:
            provider: 0720=85 ?@>20945@0 8;8 None 4;O 8A?>;L7>20=8O default
        """
        self.provider = provider or settings.default_llm_provider
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """=8F80;878@C5B :;85=B0 4;O 2K1@0==>3> ?@>20945@0"""
        if self.provider == "claude":
            from anthropic import Anthropic
            self._client = Anthropic(api_key=settings.anthropic_api_key)

        elif self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)

        elif self.provider == "perplexity":
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai"
            )

        elif self.provider == "yandex":
            from yandex_cloud_ml_sdk import YCloudML
            self._client = YCloudML(
                folder_id=settings.yandex_folder_id,
                auth=settings.yandex_api_key
            )

        elif self.provider == "gigachat":
            from gigachat import GigaChat
            self._client = GigaChat(
                credentials=settings.gigachat_api_key,
                scope=settings.gigachat_scope,
                verify_ssl_certs=False  # ;O @07@01>B:8
            )

        elif self.provider == "deepseek":
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com"
            )

        elif self.provider == "qwen":
            import dashscope
            dashscope.api_key = settings.qwen_api_key
            self._client = dashscope

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        logger.info(f"LLM Gateway initialized with provider: {self.provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Literal["text", "json"] = "text",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str | Dict[str, Any]:
        """
        #=825@A0;L=K9 2K7>2 LLM

        Args:
            prompt: "5:AB 70?@>A0
            system_prompt: !8AB5<=K9 ?@><?B (>?F8>=0;L=>)
            response_format: $>@<0B >B25B0: "text" 8;8 "json"
            temperature: "5<?5@0BC@0 35=5@0F88
            max_tokens: 0:A8<0;L=>5 :>;8G5AB2> B>:5=>2
            **kwargs: >?>;=8B5;L=K5 ?0@0<5B@K 4;O :>=:@5B=>3> ?@>20945@0

        Returns:
            str 8;8 dict 2 7028A8<>AB8 >B response_format
        """
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        logger.debug(f"LLM call to {self.provider}: prompt_length={len(prompt)}")

        try:
            if self.provider == "claude":
                response = self._call_claude(prompt, system_prompt, temperature, max_tokens, **kwargs)
            elif self.provider in ["openai", "perplexity", "deepseek"]:
                response = self._call_openai_compatible(prompt, system_prompt, temperature, max_tokens, **kwargs)
            elif self.provider == "yandex":
                response = self._call_yandex(prompt, system_prompt, temperature, max_tokens, **kwargs)
            elif self.provider == "gigachat":
                response = self._call_gigachat(prompt, system_prompt, temperature, max_tokens, **kwargs)
            elif self.provider == "qwen":
                response = self._call_qwen(prompt, system_prompt, temperature, max_tokens, **kwargs)
            else:
                raise ValueError(f"Provider {self.provider} not implemented")

            # 0@A8=3 JSON 5A;8 B@51C5BAO
            if response_format == "json":
                try:
                    return json.loads(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.debug(f"Raw response: {response}")
                    raise ValueError(f"LLM returned invalid JSON: {e}")

            return response

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _call_claude(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 Claude API"""
        messages = [{"role": "user", "content": prompt}]

        params = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        if system_prompt:
            params["system"] = system_prompt

        response = self._client.messages.create(**params)
        return response.content[0].text

    def _call_openai_compatible(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 OpenAI-A>2<5AB8<>3> API (OpenAI, Perplexity, DeepSeek)"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # >45;L 2 7028A8<>AB8 >B ?@>20945@0
        if self.provider == "openai":
            model = "gpt-4-turbo-preview"
        elif self.provider == "perplexity":
            model = "llama-3.1-sonar-large-128k-online"
        elif self.provider == "deepseek":
            model = "deepseek-chat"
        else:
            model = "gpt-4"

        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    def _call_yandex(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 YandexGPT API"""
        model = self._client.models.completions("yandexgpt")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})
        messages.append({"role": "user", "text": prompt})

        result = model.configure(temperature=temperature).run(messages)

        # 72;5:05< B5:AB 87 @57C;LB0B0
        for alternative in result:
            return alternative.text

        return ""

    def _call_gigachat(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 GigaChat API"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    def _call_qwen(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 Qwen API (Alibaba Cloud)"""
        from dashscope import Generation

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = Generation.call(
            model="qwen-max",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message'
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"Qwen API error: {response.message}")

    def count_tokens(self, text: str) -> int:
        """
        >4AGQB B>:5=>2 (?@81;878B5;L=K9)

        Args:
            text: "5:AB 4;O ?>4AGQB0

        Returns:
            @8<5@=>5 :>;8G5AB2> B>:5=>2
        """
        # @>AB0O M2@8AB8:0: ~4 A8<2>;0 = 1 B>:5= 4;O @CAA:>3> O7K:0
        return len(text) // 4

    def get_provider_info(self) -> Dict[str, Any]:
        """
        =D>@<0F8O > B5:CI5< ?@>20945@5

        Returns:
            !;>20@L A 8=D>@<0F859 > ?@>20945@5
        """
        return {
            "provider": self.provider,
            "available": self._client is not None,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens
        }


# Utility DC=:F88 4;O 8A?>;L7>20=8O 2 4@C38E <>4C;OE
def llm_call(
    prompt: str,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    response_format: Literal["text", "json"] = "text",
    **kwargs
) -> str | Dict[str, Any]:
    """
    KAB@K9 2K7>2 LLM 157 A>740=8O M:75<?;O@0 gateway

    Args:
        prompt: "5:AB 70?@>A0
        provider: @>20945@ (None 4;O default)
        system_prompt: !8AB5<=K9 ?@><?B
        response_format: $>@<0B >B25B0
        **kwargs: >?>;=8B5;L=K5 ?0@0<5B@K

    Returns:
        B25B LLM
    """
    gateway = LLMGateway(provider=provider)
    return gateway.call(
        prompt=prompt,
        system_prompt=system_prompt,
        response_format=response_format,
        **kwargs
    )


__all__ = ["LLMGateway", "llm_call"]
