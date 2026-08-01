from tenacity import wait_none

import common.llm as llm_module
from common.llm import generate_text, is_configured


def _default_kwargs() -> dict:
    return {
        "system_prompt": "system",
        "user_prompt": "user",
        "agent_name": "analyst",
        "client_id": "demo-real-estate",
        "phase": "phase_b_weekly_summary",
    }


def _fake_response(text: str):
    class FakeMessage:
        content = text

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    return FakeResponse()


def test_is_configured_false_when_key_blank(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "", raising=False)

    assert is_configured() is False


def test_is_configured_true_when_key_set(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)

    assert is_configured() is True


def test_generate_text_is_a_pure_no_op_when_unconfigured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "", raising=False)

    assert generate_text(**_default_kwargs()) is None


def test_generate_text_returns_completion_when_configured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)

    import litellm

    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kwargs: _fake_response("  Scale campaign_a, pause adset_b.  "),
    )

    result = generate_text(**_default_kwargs())

    assert result == "Scale campaign_a, pause adset_b."


def test_generate_text_retries_transient_failures_then_succeeds(monkeypatch):
    """A DeepSeek call that fails twice then succeeds must still return text.

    Matches the Media Buyer/Closer agents' own tenacity pattern: transient
    failures (rate limit, timeout) are retried, not surfaced as "no data"
    on the first hiccup.
    """

    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(llm_module._completion_with_retry.retry, "wait", wait_none())

    calls = {"count": 0}

    def _flaky(**kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("transient DeepSeek timeout")
        return _fake_response("Recovered after retries.")

    import litellm

    monkeypatch.setattr(litellm, "completion", _flaky)

    result = generate_text(**_default_kwargs())

    assert result == "Recovered after retries."
    assert calls["count"] == 3


def test_generate_text_survives_a_persistent_api_failure(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(llm_module._completion_with_retry.retry, "wait", wait_none())

    def _boom(**kwargs):
        raise RuntimeError("DeepSeek is down")

    import litellm

    monkeypatch.setattr(litellm, "completion", _boom)

    assert generate_text(**_default_kwargs()) is None
