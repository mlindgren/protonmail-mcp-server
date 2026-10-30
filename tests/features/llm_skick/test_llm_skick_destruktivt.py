"""BDD-steg för llm_skick_destruktivt.feature (gemensamma steg i conftest.py).

Koden och testerna i den här ändringen skrevs av Claude (Anthropic) för
https://github.com/mattias242/protonmail-mcp-server/issues/5.
"""
from unittest.mock import AsyncMock

from pytest_bdd import given, parsers, scenarios, then

scenarios("llm_skick_destruktivt.feature")


@given("en IMAP-klient för ett konto utan begränsningar")
def imap_without_limits(state):
    pass


@given(parsers.parse('Bridge sparar utkast i Drafts med UID "{uid}"'))
def bridge_saves_drafts(state, monkeypatch, uid):
    from protonmail_mcp import imap_drafts

    saved = []

    async def store(imap, message, message_id):
        saved.append(message)
        return uid

    async def ensure_connected():
        return None

    monkeypatch.setattr(imap_drafts, "_store_draft", store)
    state["saved_drafts"] = saved

    def setup(app):
        app.imap._ensure_connected = AsyncMock(side_effect=ensure_connected)
    state["app_setup"].append(setup)


@then("ska utkastet ha sparats i Drafts")
def draft_saved(state):
    assert len(state["saved_drafts"]) == 1


@then("ska anropet inte ha vägrats av destruktivspärren")
def not_refused_by_destructive_guard(state):
    # Anropet kan ändå falla på något annat (attrappen vägrar Bridge-kontakt,
    # argument saknas), men aldrig på PROTONMAIL_ALLOW_DESTRUCTIVE
    assert "PROTONMAIL_ALLOW_DESTRUCTIVE" not in str(state["error"] or "")
