"""Reddit market signal collector via PRAW (Reddit API).

Scans subreddits for product discussions, feature requests, complaints
and pain points — signals that indicate market gaps and unmet demand.

Requires Reddit API credentials:
  https://www.reddit.com/prefs/apps
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import praw

logger = logging.getLogger(__name__)

# Subreddits relevant to market research
DEFAULT_SUBREDDITS = [
    "SaaS",
    "startups",
    "Entrepreneur",
    "smallbusiness",
    "InternetIsBeautiful",
    "SideProject",
]

# Keywords indicating unmet demand
SIGNAL_KEYWORDS = [
    "looking for",
    "is there",
    "alternative to",
    "wish there was",
    "need a tool",
    "any recommendations",
    "frustrated with",
    "switched from",
    "pain point",
    "does anyone know",
]


@dataclass
class RedditSignal:
    """A market signal extracted from Reddit."""

    title: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    created_utc: datetime
    signal_type: str = "discussion"
    matched_keywords: list[str] = field(default_factory=list)


class RedditCollector:
    """Collects market signals from Reddit via official API.

    Args:
        client_id: Reddit app client ID.
        client_secret: Reddit app client secret.
        user_agent: User agent string for Reddit API.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str = "market-gap-scanner:v0.1.0",
    ) -> None:
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    def collect_signals(
        self,
        subreddits: list[str] | None = None,
        keywords: list[str] | None = None,
        limit_per_sub: int = 50,
        time_filter: str = "week",
    ) -> list[RedditSignal]:
        """Collect market signals from subreddits.

        Args:
            subreddits: List of subreddit names to scan.
            keywords: Signal keywords to match against.
            limit_per_sub: Max posts per subreddit.
            time_filter: Time range: hour, day, week, month, year, all.

        Returns:
            List of RedditSignal objects sorted by relevance.
        """
        subs = subreddits or DEFAULT_SUBREDDITS
        kws = [k.lower() for k in (keywords or SIGNAL_KEYWORDS)]
        signals: list[RedditSignal] = []

        for sub_name in subs:
            try:
                sub_signals = self._scan_subreddit(sub_name, kws, limit_per_sub, time_filter)
                signals.extend(sub_signals)
                logger.info("Collected %d signals from r/%s", len(sub_signals), sub_name)
            except Exception as e:
                logger.warning("Failed to scan r/%s: %s", sub_name, e)

        # Sort by engagement (score + comments)
        signals.sort(key=lambda s: s.score + s.num_comments * 2, reverse=True)
        return signals

    def _scan_subreddit(
        self,
        sub_name: str,
        keywords: list[str],
        limit: int,
        time_filter: str,
    ) -> list[RedditSignal]:
        """Scan a single subreddit for signals."""
        subreddit = self._reddit.subreddit(sub_name)
        signals = []

        for post in subreddit.top(time_filter=time_filter, limit=limit):
            title_lower = post.title.lower()
            selftext_lower = (post.selftext or "").lower()
            text = f"{title_lower} {selftext_lower}"

            matched = [kw for kw in keywords if kw in text]
            if not matched:
                continue

            signal_type = self._classify_signal(text)
            signals.append(
                RedditSignal(
                    title=post.title,
                    subreddit=sub_name,
                    score=post.score,
                    num_comments=post.num_comments,
                    url=f"https://reddit.com{post.permalink}",
                    created_utc=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                    signal_type=signal_type,
                    matched_keywords=matched,
                )
            )

        return signals

    @staticmethod
    def _classify_signal(text: str) -> str:
        """Classify the type of market signal."""
        if any(w in text for w in ["alternative to", "switched from", "moving away"]):
            return "competitor_dissatisfaction"
        if any(w in text for w in ["looking for", "need a tool", "any recommendations"]):
            return "unmet_demand"
        if any(w in text for w in ["frustrated", "pain point", "annoying"]):
            return "pain_point"
        if any(w in text for w in ["wish there was", "would pay for", "shut up and take"]):
            return "feature_request"
        return "discussion"


def format_signals(signals: list[RedditSignal], max_display: int = 20) -> str:
    """Format signals as readable report."""
    if not signals:
        return "No market signals found."

    lines = ["=" * 60, "REDDIT MARKET SIGNALS REPORT", "=" * 60, ""]

    for i, sig in enumerate(signals[:max_display], 1):
        lines.append(f"{i:3d}. [{sig.signal_type}] r/{sig.subreddit}")
        lines.append(f"     {sig.title}")
        lines.append(f"     Score: {sig.score} | Comments: {sig.num_comments}")
        lines.append(f"     Keywords: {', '.join(sig.matched_keywords)}")
        lines.append(f"     {sig.url}")
        lines.append("")

    lines.append(f"Total signals: {len(signals)}")
    return "\n".join(lines)
