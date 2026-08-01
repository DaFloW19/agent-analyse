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

    class FakeMessage:
        content = "  Scale campaign_a, pause adset_b.  "

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: FakeResponse())

    result = generate_text(**_default_kwargs())

    assert result == "Scale campaign_a, pause adset_b."


def test_generate_text_survives_an_api_failure(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)

    def _boom(**kwargs):
        raise RuntimeError("DeepSeek is down")

    import litellm

    monkeypatch.setattr(litellm, "completion", _boom)

    assert generate_text(**_default_kwargs()) is None
