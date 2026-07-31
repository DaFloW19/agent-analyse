import common.tracing as tracing_module
from common.tracing import get_langfuse_client, traced_action


def _reset_cached_client():
    tracing_module._CACHED_CLIENT_STATE["checked"] = False
    tracing_module._CACHED_CLIENT_STATE["client"] = None


def _default_traced_action():
    return traced_action(
        agent_name="analyst", client_id="demo-real-estate", phase="phase_b", model_used="rule-based"
    )


def test_get_langfuse_client_is_none_when_unconfigured(monkeypatch):
    _reset_cached_client()
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_PUBLIC_KEY", "", raising=False)
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_SECRET_KEY", "", raising=False)

    assert get_langfuse_client() is None
    _reset_cached_client()


def test_traced_action_is_a_pure_no_op_when_unconfigured(monkeypatch):
    _reset_cached_client()
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_PUBLIC_KEY", "", raising=False)
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_SECRET_KEY", "", raising=False)

    ran = False
    with _default_traced_action() as observation:
        ran = True
        assert observation is None

    assert ran is True
    _reset_cached_client()


def test_traced_action_never_swallows_business_logic_exceptions(monkeypatch):
    _reset_cached_client()
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_PUBLIC_KEY", "", raising=False)
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_SECRET_KEY", "", raising=False)

    class BoomError(Exception):
        pass

    try:
        with _default_traced_action():
            raise BoomError("business logic failed")
    except BoomError:
        pass
    else:
        raise AssertionError("traced_action must not swallow exceptions raised by the wrapped code")
    _reset_cached_client()


def test_get_langfuse_client_never_raises_when_client_construction_fails(monkeypatch):
    _reset_cached_client()
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_PUBLIC_KEY", "pk-test", raising=False)
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_SECRET_KEY", "sk-test", raising=False)
    monkeypatch.setattr(tracing_module.settings, "LANGFUSE_HOST", "not a valid host", raising=False)

    ran = False
    with _default_traced_action():
        ran = True

    assert ran is True
    _reset_cached_client()
