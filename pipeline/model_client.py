"""统一 LLM 调用客户端模块。

支持 DeepSeek、Qwen、OpenAI 三种模型提供商，通过环境变量切换。
使用 httpx 直接调用 OpenAI 兼容 API，提供重试、用量统计、成本估算等功能。
"""

import dataclasses
import enum
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMProviderType(enum.Enum):
    """LLM 提供商类型枚举。"""

    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OPENAI = "openai"


@dataclasses.dataclass
class Usage:
    """Token 使用量统计。

    Attributes:
        prompt_tokens: 输入 token 数量
        completion_tokens: 输出 token 数量
        total_tokens: 总 token 数量
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_api_response(cls, response: dict[str, Any]) -> "Usage":
        """从 API 响应构造 Usage 对象。

        Args:
            response: API 返回的 usage 字段字典。

        Returns:
            Usage 对象。
        """
        return cls(
            prompt_tokens=response.get("prompt_tokens", 0),
            completion_tokens=response.get("completion_tokens", 0),
            total_tokens=response.get("total_tokens", 0),
        )


@dataclasses.dataclass
class LLMResponse:
    """LLM 响应结果。

    Attributes:
        content: 生成的文本内容
        usage: Token 使用量统计
        model: 使用的模型名称
        provider: 提供商类型
    """

    content: str
    usage: Usage
    model: str
    provider: LLMProviderType


class CostTracker:
    """LLM 调用成本追踪器。

    追踪每次 API 调用的 token 消耗和估算成本（人民币）。
    """

    # 国产模型价格表（元/百万 tokens）
    CNY_PRICING: ClassVar[dict[LLMProviderType, tuple[float, float]]] = {
        LLMProviderType.DEEPSEEK: (1, 2),
        LLMProviderType.QWEN: (4, 12),
        LLMProviderType.OPENAI: (150, 600),
    }

    def __init__(self) -> None:
        """初始化成本追踪器。"""
        self._records: dict[LLMProviderType, list[dict[str, Any]]] = {
            p: [] for p in LLMProviderType
        }

    def record(
        self,
        usage: Usage,
        provider: LLMProviderType,
        model: str = "",
    ) -> None:
        """记录一次 API 调用。

        Args:
            usage: Token 使用量统计
            provider: 提供商类型
            model: 模型名称
        """
        self._records[provider].append({
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "model": model,
        })

    def estimated_cost(self, provider: LLMProviderType) -> float:
        """返回指定提供商的累计估算成本（元）。

        Args:
            provider: 提供商类型

        Returns:
            累计估算成本（元）
        """
        total = 0.0
        input_price, output_price = self.CNY_PRICING.get(provider, (0, 0))
        for record in self._records.get(provider, []):
            total += (record["prompt_tokens"] / 1_000_000) * input_price
            total += (record["completion_tokens"] / 1_000_000) * output_price
        return total

    def report(self, provider: Optional[LLMProviderType] = None) -> None:
        """打印成本报告。

        Args:
            provider: 提供商类型，为 None 时报告所有提供商。
        """
        providers = [provider] if provider else list(LLMProviderType)

        logger.info("=" * 50)
        logger.info("LLM 调用成本报告")
        logger.info("=" * 50)

        total_all = 0.0
        total_calls = 0
        for p in providers:
            records = self._records.get(p, [])
            if not records:
                continue

            total_tokens = sum(r["total_tokens"] for r in records)
            cost = self.estimated_cost(p)
            total_all += cost
            total_calls += len(records)

            logger.info(
                "提供商: %s | 调用次数: %d | 总 tokens: %d | 估算成本: ¥%.4f",
                p.value,
                len(records),
                total_tokens,
                cost,
            )

        logger.info("总调用次数: %d | 总成本: ¥%.4f", total_calls, total_all)
        logger.info("=" * 50)


# 全局成本追踪器实例
cost_tracker = CostTracker()


class LLMProvider(ABC):
    """LLM 提供商抽象基类。"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """发起聊天请求。

        Args:
            messages: 对话消息列表，格式为 [{"role": "user", "content": "..."}]
            model: 模型名称
            temperature: 温度参数，控制随机性
            max_tokens: 最大输出 token 数量

        Returns:
            LLMResponse 对象

        Raises:
            httpx.HTTPError: 请求失败时
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> LLMProviderType:
        """返回提供商类型。"""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API 提供商实现。

    支持 DeepSeek、Qwen 等兼容 OpenAI API 格式的服务。
    """

    # 各提供商的默认配置
    DEFAULT_CONFIGS: ClassVar[dict[LLMProviderType, dict[str, Any]]] = {
        LLMProviderType.DEEPSEEK: {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "env_key": "DEEPSEEK_API_KEY",
        },
        LLMProviderType.QWEN: {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen3.6-max-preview",
            "env_key": "QWEN_API_KEY",
        },
        LLMProviderType.OPENAI: {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "env_key": "OPENAI_API_KEY",
        },
    }

    # 定价（USD / 1M tokens）
    PRICING: ClassVar[dict[LLMProviderType, dict[str, tuple[float, float]]]] = {
        LLMProviderType.DEEPSEEK: {
            "deepseek-chat": (0.14, 0.28),  # (input, output)
            "deepseek-coder": (0.14, 0.28),
        },
        LLMProviderType.QWEN: {
            "qwen-turbo": (0.0008, 0.002),
            "qwen-plus": (0.004, 0.012),
            "qwen-max": (0.04, 0.12),
        },
        LLMProviderType.OPENAI: {
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4o": (2.50, 10.00),
            "gpt-4-turbo": (10.00, 30.00),
        },
    }

    def __init__(
        self,
        provider_type: LLMProviderType,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """初始化提供商。

        Args:
            provider_type: 提供商类型
            api_key: API 密钥，为空时从环境变量读取
            base_url: API 基础 URL，为空时使用默认值

        Raises:
            ValueError: API 密钥未配置时
        """
        self._provider_type = provider_type
        self._config = self.DEFAULT_CONFIGS[provider_type]

        if api_key is None:
            api_key = os.getenv(self._config["env_key"])
        if not api_key:
            raise ValueError(f"API key not found: {self._config['env_key']}")

        self._api_key = api_key
        self._base_url = base_url or self._config["base_url"]

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """发起聊天请求。

        Args:
            messages: 对话消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token 数量
            timeout: 请求超时时间（秒）

        Returns:
            LLMResponse 对象
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        url = f"{self._base_url}/chat/completions"

        logger.debug("Sending request to %s: model=%s", self._provider_type.value, model)

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        response = self._parse_response(data, model)
        cost_tracker.record(response.usage, self._provider_type, model)
        return response

    def _parse_response(self, data: dict[str, Any], model: str) -> LLMResponse:
        """解析 API 响应。

        Args:
            data: API 返回的 JSON 数据
            model: 请求的模型名称

        Returns:
            LLMResponse 对象
        """
        content = data["choices"][0]["message"]["content"]
        usage = Usage.from_api_response(data.get("usage", {}))

        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            provider=self._provider_type,
        )

    def get_provider_type(self) -> LLMProviderType:
        """返回提供商类型。"""
        return self._provider_type

    def get_pricing(self, model: str) -> tuple[float, float]:
        """获取模型定价。

        Args:
            model: 模型名称

        Returns:
            (输入价格, 输出价格) 元组，单位 USD / 1M tokens
        """
        provider_pricing = self.PRICING.get(self._provider_type, {})
        return provider_pricing.get(model, (0.0, 0.0))


def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    model: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLMResponse:
    """带重试机制的聊天请求。

    Args:
        provider: LLM 提供商实例
        messages: 对话消息列表
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大输出 token 数量
        max_retries: 最大重试次数
        base_delay: 重试基础延迟（秒），指数退避

    Returns:
        LLMResponse 对象

    Raises:
        httpx.HTTPError: 重试耗尽后仍然失败时
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return provider.chat(messages, model, temperature, max_tokens)
        except httpx.HTTPError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries,
                    e,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error("Request failed after %d attempts: %s", max_retries, e)

    raise last_error


def estimate_cost(
    provider: LLMProvider, model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """估算 LLM 调用成本。

    Args:
        provider: LLM 提供商实例
        model: 模型名称
        prompt_tokens: 输入 token 数量
        completion_tokens: 输出 token 数量

    Returns:
        估算成本（USD）
    """
    if isinstance(provider, OpenAICompatibleProvider):
        input_price, output_price = provider.get_pricing(model)
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price
        return input_cost + output_cost
    return 0.0


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """获取 LLM 提供商实例。

    Args:
        provider_name: 提供商类型 (deepseek/qwen/openai)，为 None 时从环境变量
            LLM_PROVIDER 读取，默认 deepseek

    Returns:
        LLMProvider 实例

    Raises:
        ValueError: 提供商类型无效或 API 密钥未配置时
    """
    if provider_name is None:
        provider_name = os.getenv("LLM_PROVIDER", "deepseek")
    provider_name = provider_name.lower()

    try:
        provider_type = LLMProviderType(provider_name)
    except ValueError:
        valid_types = [t.value for t in LLMProviderType]
        raise ValueError(
            f"Invalid LLM_PROVIDER: {provider_name}. Valid options: {valid_types}"
        )

    return OpenAICompatibleProvider(provider_type)


def quick_chat(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """便捷的聊天函数，一句话调用 LLM。

    Args:
        prompt: 用户提示词
        model: 模型名称，为空时使用提供商默认模型
        temperature: 温度参数
        max_tokens: 最大输出 token 数量

    Returns:
        LLM 生成的文本内容
    """
    provider = get_provider()

    if model is None:
        if isinstance(provider, OpenAICompatibleProvider):
            model = provider._config["default_model"]
        else:
            model = "default"

    messages = [{"role": "user", "content": prompt}]
    response = chat_with_retry(provider, messages, model, temperature, max_tokens)

    logger.info(
        "LLM call completed: model=%s, tokens=%d, cost=$%.6f",
        model,
        response.usage.total_tokens,
        estimate_cost(provider, model, response.usage.prompt_tokens, response.usage.completion_tokens),
    )

    return response.content


if __name__ == "__main__":
    # 配置日志用于测试
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 测试 quick_chat
    try:
        result = quick_chat("用一句话解释 Python 的装饰器模式。")
        print(f"\n回答: {result}")
    except Exception as e:
        logger.error("测试失败: %s", e)
