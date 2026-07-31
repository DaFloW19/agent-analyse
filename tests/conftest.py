"""Shared pytest fixtures for the Analyst test suite."""

from __future__ import annotations

import pytest

from common.db import reset_engine_for_testing
from config.settings import settings


@pytest.fixture(autouse=True, scope="session")
def _use_in_memory_test_database():
    """Force the whole test session onto an in-memory SQLite database.

    `.env`'s `DATABASE_URL` is a flat, environment-agnostic key and
    otherwise takes precedence over `config/settings.toml`'s `[testing]`
    override, which would make every logged action in the suite attempt a
    real network connection to Postgres. `settings.set(...)` has the
    highest precedence in Dynaconf, so this makes the suite deterministic
    and fast regardless of local `.env` contents.
    """

    settings.set("database_url", "sqlite+pysqlite:///:memory:")
    reset_engine_for_testing()
    yield
