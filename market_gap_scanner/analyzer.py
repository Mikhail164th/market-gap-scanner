"""Market gap analysis using Wordstat keyword volumes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .wordstat import WordstatResult


@dataclass
class MarketGap:
    """A detected market gap / opportunity."""
    keyword: str
    monthly_shows: int
    related_keywords: list[str] = field(default_factory=list)
    gap_score: float = 0.0


def analyze_gaps(results: list[WordstatResult], min_shows: int = 100, max_results: int = 50) -> list[MarketGap]:
    """Find market gaps: keywords with high demand but few alternatives.

    Gap score = shows / (1 + related_count) -- simple demand/supply ratio.
    """
    gaps: list[MarketGap] = []
    for result in results:
        for kw in result.related:
            if kw.shows < min_shows:
                continue
            related_count = len(result.related)
            gap_score = kw.shows / (1 + related_count)
            related_phrases = [r.phrase for r in result.associated[:5] if r.shows > min_shows // 2]
            gaps.append(MarketGap(keyword=kw.phrase, monthly_shows=kw.shows, related_keywords=related_phrases, gap_score=gap_score))
    gaps.sort(key=lambda g: g.gap_score, reverse=True)
    return gaps[:max_results]


def format_report(gaps: list[MarketGap]) -> str:
    if not gaps:
        return "No market gaps found for the given keywords."
    lines = ["=" * 60, "MARKET GAP ANALYSIS REPORT", "=" * 60, ""]
    for i, gap in enumerate(gaps, 1):
        lines.append(f"{i:3d}. {gap.keyword}")
        lines.append(f"     Monthly searches: {gap.monthly_shows:,}")
        lines.append(f"     Gap score: {gap.gap_score:.1f}")
        if gap.related_keywords:
            lines.append(f"     Related: {', '.join(gap.related_keywords[:3])}")
        lines.append("")
    lines.append(f"Total opportunities found: {len(gaps)}")
    return "\n".join(lines)
