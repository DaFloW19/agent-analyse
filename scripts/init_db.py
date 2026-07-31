"""One-shot script to create the central log store schema.

Usage:
    python -m scripts.init_db

Safe to re-run: table creation is idempotent. `common.db.get_engine()`
already creates the schema lazily on first use, so this script exists for
operators who want to provision the database explicitly (e.g. before the
first agent process starts) rather than relying on that first call.
"""

from __future__ import annotations

from common.db import get_engine


def main() -> None:
    """Create the `agent_logs` table (and any other declared tables)."""

    engine = get_engine()
    print(f"agent_logs schema ready at {engine.url}")


if __name__ == "__main__":
    main()
