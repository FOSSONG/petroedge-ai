"""Backward-compatible database initialisation command.

The project previously used ``Base.metadata.create_all()``. Database creation
and upgrades are now managed by Alembic so existing data can be preserved while
the schema evolves.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def init_db() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")
    print("Database migrated successfully to the latest revision.")


if __name__ == "__main__":
    init_db()
