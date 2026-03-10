"""CLI interface for Market Gap Scanner."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .analyzer import analyze_gaps, format_report
from .wordstat import WordstatClient


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="market-gap-scanner", description="Analyze market niches using Yandex Wordstat keyword data.")
    parser.add_argument("keywords", nargs="+", help="Keywords to analyze")
    parser.add_argument("--token", required=True, help="Yandex OAuth token")
    parser.add_argument("--min-shows", type=int, default=100, help="Min monthly shows (default: 100)")
    parser.add_argument("--max-results", type=int, default=50, help="Max results (default: 50)")
    parser.add_argument("--geo", type=int, nargs="*", help="Geo region IDs")
    parser.add_argument("--sandbox", action="store_true", help="Use sandbox API")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args(argv)


async def run(args):
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    async with WordstatClient(args.token, sandbox=args.sandbox) as client:
        print(f"Analyzing {len(args.keywords)} keyword(s)...")
        results = await client.get_keyword_stats(phrases=args.keywords, geo=args.geo)
        print(f"Got data for {len(results)} phrase(s), analyzing gaps...")
        gaps = analyze_gaps(results, min_shows=args.min_shows, max_results=args.max_results)
        print(format_report(gaps))


def main(argv=None):
    args = parse_args(argv)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
