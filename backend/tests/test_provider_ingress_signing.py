import time

from app.services.provider_ingress_signing import (
    build_ingress_signature,
    resolve_ingress_secret,
    verify_ingress_signature,
)


def test_ingress_signature_roundtrip(monkeypatch):
    monkeypatch.setenv("PROVIDER_RELAY_SHARED_SECRET", "test-secret")
    raw = b'{"ok":true}'
    timestamp = str(int(time.time()))
    signature = build_ingress_signature(secret="test-secret", timestamp=timestamp, raw_body=raw)
    assert verify_ingress_signature(
        secret="test-secret",
        timestamp=timestamp,
        signature=signature,
        raw_body=raw,
        tolerance_seconds=300,
    )


def test_ingress_signature_rejects_replay():
    raw = b'{"ok":true}'
    timestamp = "1"
    signature = build_ingress_signature(secret="test-secret", timestamp=timestamp, raw_body=raw)
    assert not verify_ingress_signature(
        secret="test-secret",
        timestamp=timestamp,
        signature=signature,
        raw_body=raw,
        tolerance_seconds=5,
    )


def test_resolve_ingress_secret_prefers_provider_specific(monkeypatch):
    monkeypatch.setenv("PROVIDER_RELAY_SHARED_SECRET", "generic")
    monkeypatch.setenv("RUNWAY_RELAY_SHARED_SECRET", "runway-secret")
    from importlib import reload
    import app.core.config as config_module
    reload(config_module)
    import app.services.provider_ingress_signing as ingress_module
    reload(ingress_module)
    assert ingress_module.resolve_ingress_secret("runway") == "runway-secret"
