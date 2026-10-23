"""Hjälp för HTTP-testerna: servern som ASGI-app i minnet, med attrapper i stället för Bridge.

Anropen går över riktig HTTP-semantik (httpx2 → ASGI → API-nyckelskyddet →
SDK:ns Streamable HTTP), men utan nätverk: ingen port öppnas.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from protonmail_mcp import config, http_server
from protonmail_mcp.server import AppContext, mcp, register_tools
from tests import sdk_support as sdk
from tests.mcp_resurser_support import fake_imap

TOKEN = "testnyckel-0123456789-abcdefghijklmnop"
LOCAL_HOST = "127.0.0.1:8765"

# Ett initialize-anrop som det en riktig klient skickar först
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def set_env(monkeypatch, *, token: str | None = TOKEN, allowed_hosts: str = "") -> None:
    """Inloggning, API-nyckel och värdnamn som miljövariabler (som i en LaunchAgent)."""
    monkeypatch.setenv("PROTONMAIL_USERNAME", "user")
    monkeypatch.setenv("PROTONMAIL_PASSWORD", "pass")
    monkeypatch.setenv("PROTONMAIL_WATCH_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("PROTONMAIL_HTTP_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PROTONMAIL_HTTP_TOKEN", token)
    monkeypatch.setenv("PROTONMAIL_HTTP_ALLOWED_HOSTS", allowed_hosts)
    # Testerna får inte läsa en .env från projektroten eller arbetskatalogen
    monkeypatch.setitem(config.Settings.model_config, "env_file", ())
    monkeypatch.setattr(config, "get_settings", lambda: config.Settings())


@asynccontextmanager
async def running_app(monkeypatch, *, allowed_hosts: str = ""):
    """HTTP-appen med lifespan igång och IMAP/SMTP-attrapper."""
    register_tools()
    set_env(monkeypatch, allowed_hosts=allowed_hosts)
    app_context = AppContext(imap=fake_imap(), smtp=AsyncMock())

    @asynccontextmanager
    async def lifespan(_server):
        yield app_context

    sdk.set_lifespan(monkeypatch, mcp, lifespan)
    app = http_server.build_app(mcp, config.Settings())
    async with app.lifespan():
        yield app


def http_client(app, *, host: str = LOCAL_HOST, headers: dict | None = None) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=f"http://{host}", headers=headers or {}
    )


async def post_initialize(app, *, host: str = LOCAL_HOST, headers: dict | None = None) -> httpx2.Response:
    async with http_client(app, host=host, headers=headers) as client:
        return await client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)


async def list_tools_over_http(app, *, headers: dict, host: str = LOCAL_HOST) -> list[str]:
    """Verktygsnamnen som en riktig MCP-klient ser över HTTP."""
    async with http_client(app, host=host, headers=headers) as client:
        transport = streamable_http_client(f"http://{host}/mcp", http_client=client)
        async with Client(transport, mode="legacy", cache=None) as session:
            result = sdk.wire(await session.list_tools())
    return [tool["name"] for tool in result["tools"]]


def capture_serve(monkeypatch) -> dict:
    """Byt uvicorn-starten mot en som bara fångar värd och port."""
    captured: dict = {}

    def fake_serve(app, host, port):
        captured.update(app=app, host=host, port=port)

    monkeypatch.setattr(http_server, "_serve", fake_serve)
    return captured
