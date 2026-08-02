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
    settings.set("GEMINI_API_KEY", "")
    settings.set("OPENAI_API_KEY", "")
    settings.set("LLM_MODEL", "")
    yield


@pytest.fixture(autouse=True)
def _disable_live_agent_calls(monkeypatch):
    """Make CRM Keeper / Media Buyer fetches return None by default in tests.

    Without this, every test that builds a KPI report would attempt a real
    HTTP call to localhost:8000/8004 with 3 tenacity retries each (~6s of
    backoff per unreachable service) -- slow and non-deterministic whether
    or not a developer happens to have those services running locally.
    Individual tests that need to exercise the "live" path re-monkeypatch
    `agents.analyst.live_data.fetch_crm_keeper_leads`/
    `fetch_media_buyer_spend` themselves, which overrides this for just
    that test.
    """

    import agents.analyst.live_data as live_data_module

    monkeypatch.setattr(live_data_module, "fetch_crm_keeper_leads", lambda client_id: None)
    monkeypatch.setattr(live_data_module, "fetch_media_buyer_spend", lambda: None)
    yield


@pytest.fixture(autouse=True)
def _disable_content_strategist_calls(monkeypatch):
    """Make the Content Strategist notification a no-op by default in tests.

    Same rationale as `_disable_live_agent_calls`: without this, every test
    touching a flagged landing page would attempt a real HTTP call (with
    tenacity retries) to localhost:8000. Tests that need to exercise the
    real call path re-monkeypatch
    `agents.analyst.content_strategist_notify.notify_content_strategist_of_flagged_pages`
    themselves.
    """

    import agents.analyst.content_strategist_notify as content_strategist_notify_module

    monkeypatch.setattr(
        content_strategist_notify_module,
        "notify_content_strategist_of_flagged_pages",
        lambda flagged_pages, client_id: [],
    )
    yield
