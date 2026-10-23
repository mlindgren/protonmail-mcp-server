"""Enhetstester: API-nyckelskyddet och inställningarna för HTTP-läget (http_server.py)."""
import asyncio
import logging

import pytest

from protonmail_mcp import http_server
from tests import http_support as http


async def _status(monkeypatch, *, headers=None, host=http.LOCAL_HOST, allowed_hosts=""):
    async with http.running_app(monkeypatch, allowed_hosts=allowed_hosts) as app:
        response = await http.post_initialize(app, host=host, headers=headers)
    return response.status_code


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_bearer_scheme_is_case_insensitive(monkeypatch, scheme):
    headers = {"Authorization": f"{scheme} {http.TOKEN}"}
    assert asyncio.run(_status(monkeypatch, headers=headers)) == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": f"Basic {http.TOKEN}"},
        {"Authorization": http.TOKEN},
        {"Authorization": f"Bearer {http.TOKEN[:-1]}"},
        {"Authorization": f"Bearer {http.TOKEN}x"},
        {"X-API-Key": ""},
        {"X-Api-Token": http.TOKEN},
    ],
    ids=["basic", "utan-schema", "för-kort", "för-lång", "tom", "fel-rubrik"],
)
def test_wrong_or_misplaced_key_is_denied(monkeypatch, headers):
    assert asyncio.run(_status(monkeypatch, headers=headers)) == 401


def test_one_valid_header_is_enough_even_with_a_wrong_one(monkeypatch):
    headers = {"Authorization": "Bearer fel", "X-API-Key": http.TOKEN}
    assert asyncio.run(_status(monkeypatch, headers=headers)) == 200


def test_denial_logs_header_names_but_never_values(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="protonmail_mcp.http_server")
    wrong = "Bearer " + "hemligt-men-fel-" * 3
    asyncio.run(_status(monkeypatch, headers={"Authorization": wrong}))
    assert "authorization" in caplog.text
    assert "hemligt-men-fel" not in caplog.text
    assert http.TOKEN not in caplog.text


def test_unknown_host_is_rejected_by_dns_rebinding_protection(monkeypatch):
    headers = {"Authorization": f"Bearer {http.TOKEN}"}
    status = asyncio.run(
        _status(monkeypatch, headers=headers, host="angripare.example", allowed_hosts="mcp.example.eu")
    )
    assert status == 421


def test_allowed_public_host_with_port_is_accepted(monkeypatch):
    headers = {"Authorization": f"Bearer {http.TOKEN}"}
    status = asyncio.run(
        _status(monkeypatch, headers=headers, host="mcp.example.eu:443", allowed_hosts="mcp.example.eu")
    )
    assert status == 200


def test_allowed_hosts_are_parsed_and_lowercased():
    assert http_server.parse_allowed_hosts(" A.Example.eu , ,b.example.se") == ["a.example.eu", "b.example.se"]
    assert http_server.parse_allowed_hosts("") == []


@pytest.mark.parametrize("value", ["https://a.example.eu", "*.example.eu", "a.example.eu:443", "a.example.eu/mcp"])
def test_allowed_hosts_reject_urls_wildcards_and_ports(value):
    with pytest.raises(ValueError, match="PROTONMAIL_HTTP_ALLOWED_HOSTS"):
        http_server.parse_allowed_hosts(value)


def test_token_is_not_shown_in_settings_repr(monkeypatch):
    from protonmail_mcp import config

    http.set_env(monkeypatch)
    settings = config.Settings()
    assert http.TOKEN not in repr(settings)
    assert http_server.require_token(settings) == http.TOKEN


def test_http_port_defaults_to_8765_and_is_validated(monkeypatch):
    from protonmail_mcp import config

    http.set_env(monkeypatch)
    assert config.Settings().http_port == 8765
    assert config.Settings().http_host == "127.0.0.1"
    monkeypatch.setenv("PROTONMAIL_HTTP_PORT", "70000")
    with pytest.raises(ValueError):
        config.Settings()


def test_unknown_command_line_arguments_are_ignored_as_before(monkeypatch):
    """Före --http ignorerades alla argument; en klientkonfiguration med extra
    argument ska fortfarande starta stdio-servern."""
    from protonmail_mcp import server
    from tests import sdk_support as sdk

    captured = sdk.patch_run(monkeypatch)
    server.main(["--okänt", "x"])
    assert captured["server"] is server.mcp
