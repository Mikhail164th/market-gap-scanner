"""LLM-powered market gap analysis.

Uses OpenAI SDK (compatible with any OpenAI-compatible provider:
OpenAI, Anthropic via proxy, OpenRouter, vLLM, Ollama, etc.)

Analyzes keyword volumes + Reddit signals to generate
actionable niche recommendations with confidence scoring.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    from .analyzer import MarketGap
    from .reddit import RedditSignal

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"

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
Be specific and data-driven. Avoid generic recommendations."""

ANALYSIS_PROMPT_TEMPLATE = """\
Analyze these market data sources and identify the top {max_recs} niche opportunities.

## Keyword Data (Yandex Wordstat — monthly search volumes)
{keyword_section}

## Reddit Signals (user discussions indicating market gaps)
{reddit_section}

Return a JSON object with this structure:
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


@dataclass
class NicheRecommendation:
    """AI-generated niche recommendation."""

    niche: str
    description: str
    evidence: list[str] = field(default_factory=list)
    demand_level: str = "medium"
    suggested_product: str = ""
    confidence: float = 0.5


class LLMAnalyzer:
    """Market gap analyzer powered by LLM.

    Works with any OpenAI-compatible API provider.

    Args:
        api_key: API key. Falls back to OPENAI_API_KEY env var.
        base_url: API base URL. Falls back to OPENAI_BASE_URL env var.
            Examples:
                - https://api.openai.com/v1 (OpenAI)
                - https://openrouter.ai/api/v1 (OpenRouter)
                - http://localhost:11434/v1 (Ollama)
                - http://localhost:8000/v1 (vLLM)
        model: Model name. Falls back to LLM_MODEL env var.

    Example:
        >>> analyzer = LLMAnalyzer(api_key="sk-...", model="gpt-4o-mini")
        >>> recs = analyzer.analyze(gaps=gaps, signals=signals)
        >>> print(format_recommendations(recs))
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
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

        logger.info("Calling %s for market analysis...", self._model)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
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
        # Keyword section
        kw_lines = []
        for g in gaps[:30]:
            kw_lines.append(
                f'- "{g.keyword}": {g.monthly_shows:,} searches/mo, '
                f"gap_score={g.gap_score:.1f}"
            )
        keyword_section = "\n".join(kw_lines) if kw_lines else "No keyword data available."

        # Reddit section
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
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
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
        lines.append(f"{i}. {r.niche} [{r.demand_level} demand, {r.confidence:.0%} confidence]")
        lines.append(f"   {r.description}")
        lines.append(f"   Product idea: {r.suggested_product}")
        if r.evidence:
            lines.append("   Evidence:")
            for ev in r.evidence[:3]:
                lines.append(f"     - {ev}")
        lines.append("")

    return "\n".join(lines)
