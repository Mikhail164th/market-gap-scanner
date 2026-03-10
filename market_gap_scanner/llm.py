"""LLM-powered analysis of market signals.

Uses OpenAI-compatible API to:
- Summarize market gaps from raw keyword + Reddit data
- Classify and prioritize opportunities
- Generate actionable niche recommendations
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from .analyzer import MarketGap
from .reddit import RedditSignal

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"

SYSTEM_PROMPT = """You are a market research analyst. You analyze keyword search volumes 
and social media signals to identify profitable market niches and gaps.

Your task: given keyword data (search volumes) and Reddit signals (user discussions), 
identify the most promising market opportunities. For each opportunity, explain:
1. What the gap is
2. Why it exists (evidence from data)
3. Estimated demand level
4. Suggested product/service to fill it

Be concise and data-driven. Output valid JSON."""


@dataclass
class NicheRecommendation:
    """AI-generated niche recommendation."""
    niche: str
    description: str
    evidence: list[str]
    demand_level: str  # high, medium, low
    suggested_product: str
    confidence: float


class LLMAnalyzer:
    """LLM-powered market gap analyzer.

    Args:
        api_key: OpenAI API key (or compatible provider).
        base_url: API base URL (for OpenAI-compatible providers).
        model: Model name to use.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LLMAnalyzer:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def analyze(
        self,
        gaps: list[MarketGap],
        signals: list[RedditSignal] | None = None,
        max_recommendations: int = 5,
    ) -> list[NicheRecommendation]:
        """Generate niche recommendations from market data.

        Args:
            gaps: Keyword gap analysis results.
            signals: Optional Reddit signals for richer context.
            max_recommendations: Max recommendations to generate.

        Returns:
            List of AI-generated niche recommendations.
        """
        user_prompt = self._build_prompt(gaps, signals, max_recommendations)

        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    @staticmethod
    def _build_prompt(
        gaps: list[MarketGap],
        signals: list[RedditSignal] | None,
        max_recs: int,
    ) -> str:
        parts = [f"Analyze these market data and return top {max_recs} niche opportunities as JSON.\n"]

        parts.append("## Keyword Data (Yandex Wordstat)")
        for g in gaps[:30]:
            parts.append(f"- \"{g.keyword}\": {g.monthly_shows:,} searches/mo, gap_score={g.gap_score:.1f}")

        if signals:
            parts.append("\n## Reddit Signals")
            for s in signals[:20]:
                parts.append(f"- [{s.signal_type}] r/{s.subreddit}: \"{s.title}\" (score={s.score}, comments={s.num_comments})")

        parts.append(f'\nReturn JSON: {{"recommendations": [{{"niche": "...", "description": "...", "evidence": ["..."], "demand_level": "high|medium|low", "suggested_product": "...", "confidence": 0.0-1.0}}]}}')
        return "\n".join(parts)

    @staticmethod
    def _parse_response(content: str) -> list[NicheRecommendation]:
        data = json.loads(content)
        recs = []
        for item in data.get("recommendations", []):
            recs.append(NicheRecommendation(
                niche=item.get("niche", ""),
                description=item.get("description", ""),
                evidence=item.get("evidence", []),
                demand_level=item.get("demand_level", "medium"),
                suggested_product=item.get("suggested_product", ""),
                confidence=float(item.get("confidence", 0.5)),
            ))
        return recs


def format_recommendations(recs: list[NicheRecommendation]) -> str:
    if not recs:
        return "No recommendations generated."
    lines = ["=" * 60, "AI NICHE RECOMMENDATIONS", "=" * 60, ""]
    for i, r in enumerate(recs, 1):
        lines.append(f"{i}. {r.niche} (confidence: {r.confidence:.0%})")
        lines.append(f"   {r.description}")
        lines.append(f"   Demand: {r.demand_level}")
        lines.append(f"   Product idea: {r.suggested_product}")
        if r.evidence:
            lines.append(f"   Evidence: {'; '.join(r.evidence[:3])}")
        lines.append("")
    return "\n".join(lines)
