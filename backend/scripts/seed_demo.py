"""Seed the demo analytics database.

Usage:
    python -m scripts.seed_demo                 # uses DEMO_DATABASE_URL
    python -m scripts.seed_demo --url postgresql://...  --force
"""

import argparse
import sys

from app.core.config import DATA_DIR, get_settings
from app.core.security import redact_url
from app.demo.seed import seed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="Target database URL")
    parser.add_argument("--force", action="store_true", help="Drop and recreate even if seeded")
    args = parser.parse_args()

    url = args.url or get_settings().demo_database_url
    if not url:
        print("No database URL given and DEMO_DATABASE_URL is empty.", file=sys.stderr)
        return 1
    if url.startswith("sqlite"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = seed(url, if_empty=not args.force)
    if not counts:
        print(f"{redact_url(url)} is already seeded (use --force to rebuild).")
    else:
        print(f"Seeded {redact_url(url)}:")
        for table, n in counts.items():
            print(f"  {table:<12} {n:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
