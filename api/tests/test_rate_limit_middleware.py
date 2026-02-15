from api.middleware.rate_limit import (
    _AUTH_RATE_LIMITS,
    _extract_forwarded_client_ip,
    _is_trusted_proxy_host,
    _resolve_client_ip,
)
from starlette.requests import Request


def _make_request(remote: str, xff: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if xff:
        headers.append((b"x-forwarded-for", xff.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/reading/today",
        "headers": headers,
        "client": (remote, 12345),
    }
    return Request(scope)


def test_is_trusted_proxy_host_private_ranges() -> None:
    assert _is_trusted_proxy_host("172.23.0.6")
    assert _is_trusted_proxy_host("127.0.0.1")
    assert not _is_trusted_proxy_host("8.8.8.8")


def test_extract_forwarded_client_ip_prefers_rightmost_non_proxy() -> None:
    forwarded = "198.51.100.10, 203.0.113.9, 172.23.0.6"
    assert _extract_forwarded_client_ip(forwarded) == "203.0.113.9"


def test_extract_forwarded_client_ip_ignores_invalid_entries() -> None:
    forwarded = "garbage, 999.999.999.999, 203.0.113.9"
    assert _extract_forwarded_client_ip(forwarded) == "203.0.113.9"


def test_resolve_client_ip_uses_forwarded_ip_for_trusted_proxy() -> None:
    request = _make_request("172.23.0.6", "198.51.100.10, 203.0.113.9")
    assert _resolve_client_ip(request) == "203.0.113.9"


def test_resolve_client_ip_ignores_forwarded_ip_for_untrusted_remote() -> None:
    request = _make_request("8.8.8.8", "198.51.100.10")
    assert _resolve_client_ip(request) == "8.8.8.8"


def test_auth_rate_limits_cover_sensitive_token_endpoints() -> None:
    assert "/v1/user/auth/reset-password" in _AUTH_RATE_LIMITS
    assert "/v1/user/auth/verify-email" in _AUTH_RATE_LIMITS
    assert "/v1/user/auth/resend-verification" in _AUTH_RATE_LIMITS
