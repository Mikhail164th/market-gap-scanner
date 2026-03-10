"""LLM-powered market gap analysis.

Supports multiple LLM providers:
  - **YandexGPT** (default) — Yandex Foundation Models REST API
  - **OpenAI** and compatible (OpenRouter, Ollama, vLLM, etc.) — via OpenAI SDK

Analyzes keyword volumes + Reddit signals to generate
actionable niche recommendations with confidence scoring.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .analyzer import MarketGap
    from .reddit import RedditSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a market research analyst specializing in niche discovery.

Given keyword search volume data (from Yandex Wordstat) and social media signals \
(from Reddit), identify the most promising market opportunities.

For each opportunity provide:
1. Niche name and description
2. Evidence from the data (specific keywords, discussions)
3. Demand level assessment (high/medium/low)
4. Concrete product/service suggestion to fill the gap
5. Confidence score (0.0-1.0) based on data strength

Focus on niches where demand exists but supply is insufficient. \
Be specific and data-driven. Return valid JSON."""

ANALYSIS_PROMPT_TEMPLATE = """\
Analyze these market data sources and identify the top {max_recs} niche opportunities.

## Keyword Data (Yandex Wordstat — monthly search volumes)
{keyword_section}

## Reddit Signals (user discussions indicating market gaps)
{reddit_section}

Return a JSON object:
{{
  "recommendations": [
    {{
      "niche": "Short niche name",
      "description": "What the opportunity is and why it exists",
      "evidence": ["Evidence point 1", "Evidence point 2"],
      "demand_level": "high|medium|low",
      "suggested_product": "Specific product/service idea",
      "confidence": 0.85
    }}
  ]
}}"""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class NicheRecommendation:
    """AI-generated niche recommendation."""

    niche: str
    description: str
    evidence: list[str] = field(default_factory=list)
    demand_level: str = "medium"
    suggested_product: str = ""
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# Provider base
# ---------------------------------------------------------------------------


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send a chat completion request and return the response text."""


# ---------------------------------------------------------------------------
# YandexGPT provider (REST API)
# ---------------------------------------------------------------------------

YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTProvider(BaseLLMProvider):
    """YandexGPT via Foundation Models REST API.

    Auth: either IAM token or API key.
    Model URI format: gpt://<folder_id>/<model_name>/<version>

    Args:
        folder_id: Yandex Cloud folder ID. Env: YC_FOLDER_ID.
        api_key: Yandex Cloud API key. Env: YC_API_KEY.
        iam_token: IAM token (alternative to api_key). Env: YC_IAM_TOKEN.
        model: Model name. Default: yandexgpt-lite.
        temperature: Generation temperature (0.0-1.0).
        max_tokens: Maximum response tokens.

    Example:
        >>> provider = YandexGPTProvider(
        ...     folder_id="b1g...",
        ...     api_key="AQVNxxx...",
        ... )
    """

    def __init__(
        self,
        folder_id: str | None = None,
        api_key: str | None = None,
        iam_token: str | None = None,
        model: str = "yandexgpt-lite",
        version: str = "latest",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> None:
        self._folder_id = folder_id or os.getenv("YC_FOLDER_ID", "")
        self._api_key = api_key or os.getenv("YC_API_KEY")
        self._iam_token = iam_token or os.getenv("YC_IAM_TOKEN")
        self._model_uri = f"gpt://{self._folder_id}/{model}/{version}"
        self._temperature = temperature
        self._max_tokens = max_tokens

        if not self._api_key and not self._iam_token:
            raise ValueError(
                "YandexGPT requires either api_key (YC_API_KEY) "
                "or iam_token (YC_IAM_TOKEN)"
            )

    def complete(self, system: str, user: str) -> str:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Api-Key {self._api_key}"
        else:
            headers["Authorization"] = f"Bearer {self._iam_token}"

        payload = {
            "modelUri": self._model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": self._temperature,
                "maxTokens": str(self._max_tokens),
            },
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }

        resp = httpx.post(
            YANDEX_API_URL,
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        alternatives = data.get("result", {}).get("alternatives", [])
        if not alternatives:
            raise ValueError("Empty response from YandexGPT")

        return alternatives[0]["message"]["text"]


# ---------------------------------------------------------------------------
# OpenAI provider (SDK)
# ---------------------------------------------------------------------------


class OpenAIProvider(BaseLLMProvider):
    """OpenAI and compatible providers via official SDK.

    Works with: OpenAI, OpenRouter, Ollama, vLLM, LM Studio, etc.

    Args:
        api_key: API key. Env: OPENAI_API_KEY.
        base_url: API base URL. Env: OPENAI_BASE_URL.
        model: Model name. Env: LLM_MODEL. Default: gpt-4o-mini.

    Example:
        >>> provider = OpenAIProvider(api_key="sk-...")
        >>> # OpenRouter:
        >>> provider = OpenAIProvider(
        ...     api_key="sk-or-...",
        ...     base_url="https://openrouter.ai/api/v1",
        ...     model="deepseek/deepseek-chat",
        ... )
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        from openai import OpenAI

        self._model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


class LLMAnalyzer:
    """Market gap analyzer powered by LLM.

    Auto-detects provider from environment:
      - If YC_API_KEY or YC_IAM_TOKEN set → YandexGPT
      - If OPENAI_API_KEY set → OpenAI
      - Or pass provider explicitly.

    Args:
        provider: LLM provider instance. Auto-detected if None.

    Example:
        >>> # Auto-detect (YandexGPT if YC_API_KEY set)
        >>> analyzer = LLMAnalyzer()
        >>>
        >>> # Explicit YandexGPT
        >>> analyzer = LLMAnalyzer(provider=YandexGPTProvider(
        ...     folder_id="b1g...", api_key="AQV..."
        ... ))
        >>>
        >>> # Explicit OpenAI
        >>> analyzer = LLMAnalyzer(provider=OpenAIProvider(api_key="sk-..."))
        >>>
        >>> recs = analyzer.analyze(gaps=gaps, signals=signals)
        >>> print(format_recommendations(recs))
    """

    def __init__(self, provider: BaseLLMProvider | None = None) -> None:
        self._provider = provider or self._auto_detect_provider()

    @staticmethod
    def _auto_detect_provider() -> BaseLLMProvider:
        """Auto-detect LLM provider from environment variables."""
        if os.getenv("YC_API_KEY") or os.getenv("YC_IAM_TOKEN"):
            logger.info("Using YandexGPT provider")
            return YandexGPTProvider()
        if os.getenv("OPENAI_API_KEY"):
            logger.info("Using OpenAI provider")
            return OpenAIProvider()
        raise ValueError(
            "No LLM provider configured. Set YC_API_KEY (YandexGPT) "
            "or OPENAI_API_KEY (OpenAI/compatible)."
        )

    def analyze(
        self,
        gaps: list[MarketGap],
        signals: list[RedditSignal] | None = None,
        max_recommendations: int = 5,
    ) -> list[NicheRecommendation]:
        """Generate niche recommendations from collected market data.

        Args:
            gaps: Keyword gap analysis results from Wordstat.
            signals: Optional Reddit signals for richer context.
            max_recommendations: Maximum recommendations to generate.

        Returns:
            Sorted list of NicheRecommendation (highest confidence first).
        """
        prompt = self._build_prompt(gaps, signals, max_recommendations)

        logger.info("Requesting LLM analysis (%s)...", type(self._provider).__name__)
        content = self._provider.complete(SYSTEM_PROMPT, prompt)

        if not content:
            logger.warning("Empty LLM response")
            return []

        return self._parse_response(content)

    @staticmethod
    def _build_prompt(
        gaps: list[MarketGap],
        signals: list[RedditSignal] | None,
        max_recs: int,
    ) -> str:
        kw_lines = []
        for g in gaps[:30]:
            kw_lines.append(
                f'- "{g.keyword}": {g.monthly_shows:,} searches/mo, '
                f"gap_score={g.gap_score:.1f}"
            )
        keyword_section = "\n".join(kw_lines) if kw_lines else "No keyword data available."

        rd_lines = []
        if signals:
            for s in signals[:20]:
                rd_lines.append(
                    f"- [{s.signal_type}] r/{s.subreddit}: "
                    f'"{s.title}" (upvotes={s.score}, comments={s.num_comments})'
                )
        reddit_section = "\n".join(rd_lines) if rd_lines else "No Reddit signals available."

        return ANALYSIS_PROMPT_TEMPLATE.format(
            max_recs=max_recs,
            keyword_section=keyword_section,
            reddit_section=reddit_section,
        )

    @staticmethod
    def _parse_response(content: str) -> list[NicheRecommendation]:
        # YandexGPT may wrap JSON in markdown code blocks
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON:\n%s", content[:500])
            return []

        recs = []
        for item in data.get("recommendations", []):
            recs.append(
                NicheRecommendation(
                    niche=item.get("niche", ""),
                    description=item.get("description", ""),
                    evidence=item.get("evidence", []),
                    demand_level=item.get("demand_level", "medium"),
                    suggested_product=item.get("suggested_product", ""),
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        recs.sort(key=lambda r: r.confidence, reverse=True)
        return recs


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_recommendations(recs: list[NicheRecommendation]) -> str:
    """Format recommendations as a readable report."""
    if not recs:
        return "No recommendations generated."

    lines = [
        "=" * 60,
        "AI NICHE RECOMMENDATIONS",
        "=" * 60,
        "",
    ]

    for i, r in enumerate(recs, 1):
        lines.append(
            f"{i}. {r.niche} [{r.demand_level} demand, {r.confidence:.0%} confidence]"
        )
        lines.append(f"   {r.description}")
        lines.append(f"   Product idea: {r.suggested_product}")
        if r.evidence:
            lines.append("   Evidence:")
            for ev in r.evidence[:3]:
                lines.append(f"     - {ev}")
        lines.append("")

    return "\n".join(lines)
