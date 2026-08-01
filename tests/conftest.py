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


@pytest.fixture(autouse=True, scope="session")
def _disable_real_external_credentials():
    """Force Langfuse and DeepSeek credentials blank for the whole suite.

    A developer's real `.env` (added once real keys exist for manual
    testing) would otherwise leak into every test: each traced action
    would attempt a real Langfuse network call, and every
    `build_weekly_optimisation_report()` call would attempt a real,
    billed DeepSeek completion -- slow, non-deterministic, and
    potentially costly. Individual tests that need to exercise the
    "configured" path still monkeypatch these back on for just that test.
    """

    settings.set("LANGFUSE_PUBLIC_KEY", "")
    settings.set("LANGFUSE_SECRET_KEY", "")
    settings.set("DEEPSEEK_API_KEY", "")
    yield
