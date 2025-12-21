from __future__ import annotations

import argparse

from . import generate_feed, scrape_channel_stats, scrape_videos


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytsubs",
        description="YouTube subscriptions scraping and feed generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape_videos_parser = subparsers.add_parser(
        "scrape-videos",
        help="Scrape subscription feed videos.",
    )
    scrape_videos_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in non-headless mode.",
    )
    scrape_videos_parser.add_argument(
        "--no-generate-feed",
        action="store_true",
        help="Skip generating the feed after scraping.",
    )
    scrape_videos_parser.set_defaults(func=_run_scrape_videos)

    scrape_channels_parser = subparsers.add_parser(
        "scrape-channels",
        help="Scrape channel statistics from subscriptions.",
    )
    scrape_channels_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in non-headless mode.",
    )
    scrape_channels_parser.set_defaults(func=_run_scrape_channels)

    open_feed_parser = subparsers.add_parser(
        "open",
        help="Open the latest generated feed.",
    )
    open_feed_parser.set_defaults(func=_run_open_feed)

    debug_scrape_parser = subparsers.add_parser(
        "debug-scrape",
        help="Debug the subscriptions feed scraper.",
    )
    debug_scrape_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run with visible browser window.",
    )
    debug_scrape_parser.add_argument(
        "--scrolls",
        type=int,
        default=6,
        help="Number of scroll batches to capture.",
    )
    debug_scrape_parser.add_argument(
        "--filter",
        dest="title_filter",
        help="Optional case-insensitive substring to filter titles.",
    )
    debug_scrape_parser.set_defaults(func=_run_debug_scrape)

    return parser


def _run_scrape_videos(args: argparse.Namespace) -> int:
    scrape_videos.run(
        debug=args.debug,
        generate_feed_after=not args.no_generate_feed,
    )
    return 0


def _run_scrape_channels(args: argparse.Namespace) -> int:
    scrape_channel_stats.run(debug=args.debug)
    return 0


def _run_open_feed(args: argparse.Namespace) -> int:
    opened = generate_feed.open_feed()
    return 0 if opened else 1


def _run_debug_scrape(args: argparse.Namespace) -> int:
    from . import debug_scrape

    debug_scrape.run(
        debug=args.debug,
        scrolls=args.scrolls,
        title_filter=args.title_filter,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
