from tenacity import wait_none

import agents.analyst.live_data as live_data_module
from agents.analyst.live_data import (
    CRM_KEEPER_STAGES,
    fetch_crm_keeper_leads,
    fetch_media_buyer_spend,
)


def test_fetch_crm_keeper_leads_returns_none_when_unreachable(monkeypatch):
    def _boom(url, **kwargs):
        raise RuntimeError("CRM Keeper is down")

    monkeypatch.setattr(live_data_module, "_get_json", _boom)

    assert fetch_crm_keeper_leads("demo-real-estate") is None


def test_fetch_crm_keeper_leads_aggregates_across_stages(monkeypatch):
    def _fake_get_json(url, params=None):
        stage = url.rsplit("/", 1)[-1]
        return [
            {
                "lead_id": f"ld_{stage}",
                "qualification_score": 42,
                "lead_stage": stage,
                "created_at": "2026-08-01T00:00:00Z",
            }
        ]

    monkeypatch.setattr(live_data_module, "_get_json", _fake_get_json)

    leads = fetch_crm_keeper_leads("demo-real-estate")

    assert leads is not None
    assert len(leads) == len(CRM_KEEPER_STAGES)
    assert {lead["lead_stage"] for lead in leads} == set(CRM_KEEPER_STAGES)
    assert all(lead["score"] == 42 for lead in leads)
    assert all(lead["data_as_of"] == "2026-08-01T00:00:00Z" for lead in leads)


def test_fetch_media_buyer_spend_returns_none_when_unreachable(monkeypatch):
    def _boom(url, **kwargs):
        raise RuntimeError("Media Buyer is down")

    monkeypatch.setattr(live_data_module, "_get_json", _boom)

    assert fetch_media_buyer_spend() is None


def test_fetch_media_buyer_spend_returns_spend_value(monkeypatch):
    monkeypatch.setattr(
        live_data_module,
        "_get_json",
        lambda url, **kwargs: {
            "status": "success",
            "data": {"spend": 342.17, "impressions": 58210, "clicks": 1032, "leads": 47},
        },
    )

    result = fetch_media_buyer_spend()

    assert result is not None
    assert result["spend"] == 342.17
    assert result["data_as_of"]


def test_get_json_retries_transient_failures_then_succeeds(monkeypatch):
    monkeypatch.setattr(live_data_module._get_json.retry, "wait", wait_none())

    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("transient network error")
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", lambda timeout=None: FakeClient())

    result = live_data_module._get_json("http://example.test")

    assert result == {"ok": True}
    assert calls["count"] == 3
