from types import SimpleNamespace

from app.core.config import settings
from app.core.rate_limit_middleware import client_ip


def _request(forwarded=None, direct="10.0.0.1"):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=direct), headers=headers)


def test_without_trusted_proxies_the_header_is_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 0)

    assert client_ip(_request("203.0.113.9")) == "10.0.0.1"


def test_one_trusted_proxy_uses_the_last_forwarded_address(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)

    # A client can prepend fake entries; only the proxy-added one is trusted.
    request = _request("198.51.100.7, 203.0.113.9")

    assert client_ip(request) == "203.0.113.9"


def test_missing_header_falls_back_to_the_direct_address(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)

    assert client_ip(_request()) == "10.0.0.1"
