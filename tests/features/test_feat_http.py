"""BDD: servern över HTTP (Streamable HTTP) med API-nyckel, för Perplexity bakom Cloudflare Access."""
import asyncio
import logging

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from protonmail_mcp import server
from tests import http_support as http
from tests import sdk_support as sdk

scenarios("feat_http.feature")


@pytest.fixture
def state():
    return {"allowed_hosts": ""}


@given("servern körs i HTTP-läge med en API-nyckel")
def http_mode(monkeypatch, state):
    http.set_env(monkeypatch)


@given(parsers.parse('servern körs i HTTP-läge med en API-nyckel och värdnamnet "{host}"'))
def http_mode_with_host(monkeypatch, state, host):
    http.set_env(monkeypatch, allowed_hosts=host)
    state["allowed_hosts"] = host


@given("ingen API-nyckel är satt")
def no_token(monkeypatch):
    http.set_env(monkeypatch, token=None)


@given(parsers.parse('API-nyckeln är "{token}"'))
def short_token(monkeypatch, token):
    http.set_env(monkeypatch, token=token)


async def _initialize(monkeypatch, state, *, headers=None, host=http.LOCAL_HOST):
    async with http.running_app(monkeypatch, allowed_hosts=state["allowed_hosts"]) as app:
        return await http.post_initialize(app, host=host, headers=headers)


@when("en klient anropar /mcp utan nyckel")
def call_without_key(monkeypatch, state):
    state["response"] = asyncio.run(_initialize(monkeypatch, state))


@when("en klient anropar /mcp med fel nyckel")
def call_with_wrong_key(monkeypatch, state):
    headers = {"Authorization": "Bearer " + "x" * len(http.TOKEN)}
    state["response"] = asyncio.run(_initialize(monkeypatch, state, headers=headers))


@when(parsers.parse('en klient anropar /mcp via "{host}" med rätt nyckel'))
def call_via_host(monkeypatch, state, host):
    headers = {"Authorization": f"Bearer {http.TOKEN}"}
    state["response"] = asyncio.run(_initialize(monkeypatch, state, headers=headers, host=host))


def _key_headers(header: str) -> dict:
    if header == "Authorization: Bearer":
        return {"Authorization": f"Bearer {http.TOKEN}"}
    return {header: http.TOKEN}


async def _tools(monkeypatch, state, headers, host=http.LOCAL_HOST):
    async with http.running_app(monkeypatch, allowed_hosts=state["allowed_hosts"]) as app:
        return await http.list_tools_over_http(app, headers=headers, host=host)


@when(parsers.parse('en MCP-klient ansluter över HTTP med nyckeln som "{header}"'))
@when(parsers.parse('en MCP-klient ansluter över HTTP med nyckeln i "{header}"'))
def connect_with_key(monkeypatch, state, header):
    state["tools"] = asyncio.run(_tools(monkeypatch, state, _key_headers(header)))


@when(parsers.parse('en MCP-klient ansluter över HTTP via "{host}" med nyckeln som "{header}"'))
def connect_via_host(monkeypatch, state, host, header):
    state["tools"] = asyncio.run(_tools(monkeypatch, state, _key_headers(header), host=host))


@then("ska svaret vara 401")
def is_401(state):
    assert state["response"].status_code == 401


@then("ska svaret inte innehålla något från MCP-servern")
def no_mcp_content(state):
    body = state["response"].text
    assert "jsonrpc" not in body and "protonmail" not in body


@then("ska svaret inte vara 200")
def not_200(state):
    assert state["response"].status_code != 200


@then(parsers.parse("ska klienten se {count:d} verktyg"))
def sees_tools(state, count):
    assert len(state["tools"]) == count


@when(parsers.parse('servern startas med "{flag}"'))
def start_with_flag(monkeypatch, state, caplog):
    state["serve"] = http.capture_serve(monkeypatch)
    caplog.set_level(logging.ERROR)
    try:
        server.main(["--http"])
    except SystemExit as exc:
        state["exit"] = exc
    state["log"] = caplog.text


@when("servern startas utan flaggor")
def start_without_flags(monkeypatch, state):
    http.set_env(monkeypatch)
    state["serve"] = http.capture_serve(monkeypatch)
    state["run"] = sdk.patch_run(monkeypatch)
    server.main([])


@then(parsers.parse('ska den avsluta med ett fel som nämner "{text}"'))
def exits_with_error(state, text):
    assert "exit" in state, "servern startade trots felet"
    assert state["exit"].code not in (0, None)
    assert text in state["log"]
    assert http.TOKEN not in state["log"]


@then("ska ingen HTTP-server ha startats")
def no_http_server(state):
    assert state["serve"] == {}


@then("ska den lyssna på 127.0.0.1")
def listens_on_localhost(state):
    assert "exit" not in state
    assert state["serve"]["host"] == "127.0.0.1"


@then("ska den köras över stdio")
def runs_stdio(state):
    assert state["serve"] == {}
    assert state["run"]["server"] is server.mcp
