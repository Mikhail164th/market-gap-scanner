"""CLI interface for Market Gap Scanner."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .analyzer import analyze_gaps, format_report
from .wordstat import WordstatClient


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="market-gap-scanner",
        description="Analyze market niches using Yandex Wordstat, Reddit, and LLM.",
    )
    parser.add_argument(
        "keywords", nargs="+", help="Keywords to analyze",
    )

    # Wordstat options
    ws = parser.add_argument_group("Wordstat")
    ws.add_argument("--token", required=True, help="Yandex OAuth token")
    ws.add_argument("--geo", type=int, nargs="*", help="Geo region IDs")
    ws.add_argument("--sandbox", action="store_true", help="Use Yandex sandbox API")

    # Reddit options
    rd = parser.add_argument_group("Reddit")
    rd.add_argument("--reddit-id", help="Reddit app client_id")
    rd.add_argument("--reddit-secret", help="Reddit app client_secret")
    rd.add_argument(
        "--subreddits", nargs="*",
        default=["SaaS", "startups", "Entrepreneur"],
        help="Subreddits to scan (default: SaaS startups Entrepreneur)",
    )

    # LLM options
    llm = parser.add_argument_group("LLM analysis")
    llm.add_argument(
        "--llm", action="store_true",
        help="Enable LLM-powered recommendations (requires API key in env)",
    )

    # General options
    parser.add_argument("--min-shows", type=int, default=100, help="Min monthly shows (default: 100)")
    parser.add_argument("--max-results", type=int, default=50, help="Max results (default: 50)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    """Run the market gap analysis pipeline."""
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Step 1: Wordstat keyword volumes
    print(f"Analyzing {len(args.keywords)} keyword(s) via Wordstat...")
    async with WordstatClient(args.token, sandbox=args.sandbox) as client:
        results = await client.get_keyword_stats(phrases=args.keywords, geo=args.geo)

    gaps = analyze_gaps(results, min_shows=args.min_shows, max_results=args.max_results)
    print(format_report(gaps))

    # Step 2: Reddit signals (optional)
    signals = None
    if args.reddit_id and args.reddit_secret:
        from .reddit import RedditCollector, format_signals

        print(f"\nScanning {len(args.subreddits)} subreddit(s) for market signals...")
        collector = RedditCollector(
            client_id=args.reddit_id,
            client_secret=args.reddit_secret,
        )
        signals = collector.collect_signals(
            subreddits=args.subreddits,
            keywords=args.keywords,
        )
        print(format_signals(signals))

    # Step 3: LLM recommendations (optional)
    if args.llm and gaps:
        from .llm import LLMAnalyzer, format_recommendations

        print("\nGenerating AI recommendations...")
        analyzer = LLMAnalyzer()
        recs = analyzer.analyze(gaps=gaps, signals=signals)
        print(format_recommendations(recs))


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = parse_args(argv)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
