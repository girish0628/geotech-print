"""Tests for FMEWebhookService."""
import pytest
import requests
from src.services.fme_webhook_service import FMEWebhookService
from src.core.exceptions import FMEWebhookError


class FakeResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self):
        pass

    @property
    def headers(self):
        return {"content-type": "application/json"}

    def json(self):
        return {"status": "SUCCESS"}


def test_trigger_success(monkeypatch):
    """trigger^(^) returns parsed JSON on success."""
    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse())

    svc = FMEWebhookService(webhook_url="https://fme.test/webhook", timeout_s=10)
    result = svc.trigger(payload={"key": "value"})

    assert result["status"] == "SUCCESS"


def test_trigger_raises_on_network_error(monkeypatch):
    """trigger^(^) raises FMEWebhookError on network failure."""

    def fail(*a, **kw):
        raise requests.RequestException("connection error")

    monkeypatch.setattr(requests, "post", fail)

    svc = FMEWebhookService(webhook_url="https://fme.test/webhook", timeout_s=10)
    with pytest.raises(FMEWebhookError):
        svc.trigger(payload={})
