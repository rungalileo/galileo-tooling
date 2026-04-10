import argparse
import asyncio
import logging

from astra.commands.review import cmd_review


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(prog="astra", description="Astra job runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Code review of a PR")
    review.add_argument("pr_url", help="GitHub PR URL (e.g. https://github.com/owner/repo/pull/123)")
    review.set_defaults(func=cmd_review)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
