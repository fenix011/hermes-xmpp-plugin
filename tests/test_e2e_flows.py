"""End-to-end flow tests for the XMPP adapter.

These exercises the inbound → outbound pipeline with realistic slixmpp
stanzas, verifying that MessageEvent fields, reply context, authorization,
reactions, and send() routing all wire together correctly.

Run: python -m pytest tests/test_e2e_flows.py -v
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import unittest.mock

# -----------------------------------------------------------------
# Mock gateway / tools so adapter.py imports cleanly
# -----------------------------------------------------------------

gateway_mod = unittest.mock.MagicMock()
sys.modules["gateway"] = gateway_mod

gw_config = unittest.mock.MagicMock()
sys.modules["gateway.config"] = gw_config
gw_config.Platform = type("Platform", (), {"__init__": lambda self, *a, **k: None})
gw_config.PlatformConfig = type("PlatformConfig", (), {"__init__": lambda self, *a, **k: None})

gw_platforms = unittest.mock.MagicMock()
sys.modules["gateway.platforms"] = gw_platforms

gw_base = unittest.mock.MagicMock()
sys.modules["gateway.platforms.base"] = gw_base

class _FakeMessageEvent:
    def __init__(self, *, text="", message_type=None, source=None, raw_message=None,
                 message_id=None, reply_to_message_id=None, reply_to_text=None, metadata=None):
        self.text = text
        self.message_type = message_type
        self.source = source
        self.raw_message = raw_message
        self.message_id = message_id
        self.reply_to_message_id = reply_to_message_id
        self.reply_to_text = reply_to_text
        self.metadata = metadata or {}

gw_base.MessageEvent = _FakeMessageEvent
gw_base.MessageType = type("MessageType", (), {"TEXT": "text", "IMAGE": "image", "COMMAND": "command"})

class _FakeProcessingOutcome:
    SUCCESS = 0
    FAILURE = 1
    CANCELLED = 2

gw_base.ProcessingOutcome = _FakeProcessingOutcome
gw_base.SendResult = type("SendResult", (), {
    "__init__": lambda s, **kw: s.__dict__.update(kw) or None,
})

# Track calls into BasePlatformAdapter for assertions
captured_handle_calls = []

def _capture_handle_message(self, event):
    captured_handle_calls.append(event)
gw_base.BasePlatformAdapter = type("BasePlatformAdapter", (), {
    "__init__": lambda s, *a, **k: setattr(s, "config", a[0] if a else None) or None,
    "emit_message_raw": lambda *a, **kw: None,
    "on_processing_start": lambda *a, **kw: None,
    "on_processing_complete": lambda *a, **kw: None,
    "send": lambda *a, **kw: None,
    "handle_message": _capture_handle_message,
    "build_source": lambda s, **kw: MagicMock(**kw),
    "_mark_disconnected": lambda s: None,
    "fatal_error_message": lambda s: getattr(s, "_fatal_msg", None),
})

gw_models = unittest.mock.MagicMock()
sys.modules["gateway.platforms.models"] = gw_models
class _FakeChatContext:
    def __init__(self, **kw):
        pass
gw_models.ChatContext = _FakeChatContext

gw_util = unittest.mock.MagicMock()
sys.modules["gateway.util"] = gw_util

tools_mod = unittest.mock.MagicMock()
sys.modules["tools"] = tools_mod
tools_gateway = unittest.mock.MagicMock()
sys.modules["tools.clarify_gateway"] = tools_gateway
tools_gateway.mark_awaiting_text = unittest.mock.MagicMock()

slixmpp_omemo_mod = unittest.mock.MagicMock()
sys.modules["slixmpp_omemo"] = slixmpp_omemo_mod
slixmpp_omemo_mod.TrustLevel = type("TrustLevel", (), {})
slixmpp_omemo_mod.XEP_0384 = type("XEP_0384", (), {})

omemo_mod = unittest.mock.MagicMock()
sys.modules["omemo"] = omemo_mod
omemo_storage = unittest.mock.MagicMock()
sys.modules["omemo.storage"] = omemo_storage
class _FakeStorage:
    def __init__(self): pass
    async def _load(self, key): pass
    async def _store(self, key, value): pass
omemo_storage.Just = type("Just", (), {"__init__": lambda self, *a, **k: None})
omemo_storage.Maybe = type("Maybe", (), {})
omemo_storage.Nothing = type("Nothing", (), {"__init__": lambda self, *a, **k: None})
omemo_storage.Storage = _FakeStorage

omemo_types = unittest.mock.MagicMock()
sys.modules["omemo.types"] = omemo_types
omemo_types.DeviceInformation = type("DeviceInformation", (), {})
omemo_types.JSONType = type("JSONType", (), {})

# Force a fresh import so we don't inherit a broken BasePlatformAdapter from another test file's cache
if "adapter" in sys.modules:
    del sys.modules["adapter"]
for key in list(sys.modules.keys()):
    if key.startswith("adapter."):
        del sys.modules[key]

import adapter  # noqa: E402

ProcessingOutcome = _FakeProcessingOutcome


def _create_stanza(fields):
    """Create a fake stanza whose __getitem__ actually works."""
    class _FakeStanza:
        def __getitem__(self, k):
            return fields.get(k, "")
        def get(self, k, default=None):
            return fields.get(k, default)
        def get_from(self):
            return fields.get("from_jid", "user@example.org")
    return _FakeStanza()


def _make_stanza(**fields):
    """Build a fake slixmpp Message stanza."""
    return _create_stanza(fields)


def _make_reply_stanza(reply_id="orig-id", body="> prior\nresponse"):
    """Build a stanza that carries a XEP-0461 <reply>."""
    reply_elem = MagicMock()
    reply_elem.get = lambda k, default=None: {"id": reply_id}.get(k, default)
    reply_elem.strip_fallback_content = lambda: "> prior"

    fields = {"reply": reply_elem, "body": body, "type": "chat", "id": "stanza-reply-1"}
    class _FakeStanza:
        def __getitem__(self, k):
            return fields.get(k, "")
        def get(self, k, default=None):
            return fields.get(k, default)
        def get_from(self):
            return "user@example.org"
    return _FakeStanza()


# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------

@pytest.fixture
def adapter_instance():
    """Return a connected XmppAdapter with a fake client."""
    cfg = MagicMock()
    cfg.jid = "hermes@example.org"
    cfg.password = "secret"
    cfg.home_channel = None
    cfg.fileserver_url = None

    a = adapter.XmppAdapter(cfg)
    a.allow_all_users = True
    a._self_bare = "hermes@example.org"
    a._known_mucs = {"room@conference.example.org"}
    a._registered_plugins = {
        "xep_0030", "xep_0045", "xep_0066", "xep_0085",
        "xep_0199", "xep_0363",
        "xep_0394", "xep_0444", "xep_0004",
        "xep_0050", "xep_0461", "xep_0446", "xep_0447",
    }

    client = MagicMock()
    client.boundjid.bare = "hermes@example.org"
    client.plugins = {}
    client.__getitem__ = lambda s, k: client.plugins.get(k)
    client.__contains__ = lambda s, k: k in client.plugins
    client.make_message = MagicMock(return_value=MagicMock())
    client.send_message = MagicMock(return_value=MagicMock())
    a.client = client
    a._session_ready = asyncio.Event()
    a._session_ready.set()
    a._pending_reactions = {}
    return a


@pytest.fixture(autouse=True)
def clear_captured():
    captured_handle_calls.clear()
    yield
    captured_handle_calls.clear()


# -----------------------------------------------------------------
# Inbound → Event flow
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_inbound_chat_message_creates_event(adapter_instance):
    stanza = _make_stanza(
        type="chat",
        body="hello bot",
        from_jid="user@example.org",
        id="msg-1",
    )
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 1
    evt = captured_handle_calls[0]
    assert evt.text == "hello bot"
    assert evt.message_id == "msg-1"
    assert evt.source.chat_id == "user@example.org"
    assert evt.source.chat_type == "dm"


@pytest.mark.asyncio
async def test_inbound_groupchat_message_creates_event(adapter_instance):
    stanza = _make_stanza(
        type="groupchat",
        body="room hello",
        from_jid="room@conference.example.org/nick",
        id="msg-2",
        muc={"jid": "real@example.org"},
    )
    fields = {
        "type": "groupchat",
        "body": "room hello",
        "from_jid": "room@conference.example.org/nick",
        "id": "msg-2",
        "muc": {"jid": "real@example.org"},
    }
    class _FakeStanza:
        def __getitem__(self, k):
            return fields.get(k, "")
        def get(self, k, default=None):
            return fields.get(k, default)
        def get_from(self):
            return fields.get("from_jid", "")

    stanza = _FakeStanza()
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 1
    evt = captured_handle_calls[0]
    assert evt.text == "room hello"
    assert evt.source.chat_type == "group"
    assert "room@conference.example.org" in evt.source.chat_id


@pytest.mark.asyncio
async def test_self_message_is_ignored(adapter_instance):
    stanza = _make_stanza(
        type="chat",
        body="echo",
        from_jid="hermes@example.org",
        id="msg-3",
    )
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 0


@pytest.mark.asyncio
async def test_error_headline_stanzas_are_ignored(adapter_instance):
    for stype in ("error", "headline"):
        stanza = _make_stanza(type=stype, body="x", from_jid="user@example.org")
        await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 0


@pytest.mark.asyncio
async def test_empty_body_is_ignored(adapter_instance):
    stanza = _make_stanza(type="chat", body="", from_jid="user@example.org")
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 0


@pytest.mark.asyncio
async def test_unauthorized_message_is_dropped(adapter_instance):
    adapter_instance.allow_all_users = False
    adapter_instance.allowed_users = {"other@example.org"}
    stanza = _make_stanza(type="chat", body="secret", from_jid="user@example.org")
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 0


# -----------------------------------------------------------------
# Reply context extraction (XEP-0461 inbound)
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_reply_stanza_populates_reply_fields(adapter_instance):
    stanza = _make_reply_stanza(reply_id="orig-42", body="> prior\nmy answer")
    await adapter_instance._on_message(stanza)
    assert len(captured_handle_calls) == 1
    evt = captured_handle_calls[0]
    assert evt.reply_to_message_id == "orig-42"
    assert evt.reply_to_text == "> prior"


# -----------------------------------------------------------------
# Outbound send routing
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_uses_xep_0461_when_reply_to_provided(adapter_instance):
    client = adapter_instance.client
    client.plugins["xep_0461"] = MagicMock()
    stanza = MagicMock()
    client.plugins["xep_0461"].make_reply.return_value = stanza
    result = await adapter_instance.send(chat_id="user@example.org", content="hi", reply_to="orig-id")
    assert result.success is True
    client.plugins["xep_0461"].make_reply.assert_called_once()
    assert client.plugins["xep_0461"].make_reply.call_args.kwargs["reply_id"] == "orig-id"
    assert client.plugins["xep_0461"].make_reply.call_args.kwargs["mto"] == "user@example.org"
    stanza.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_uses_plain_send_message_without_reply_to(adapter_instance):
    client = adapter_instance.client
    result = await adapter_instance.send(chat_id="user@example.org", content="hi")
    assert result.success is True
    client.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_returns_failure_when_disconnected(adapter_instance):
    adapter_instance.client = None
    result = await adapter_instance.send(chat_id="user@example.org", content="hi")
    assert result.success is False
    assert "not connected" in result.error.lower()


# -----------------------------------------------------------------
# Reaction lifecycle hooks
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaction_lifecycle_from_start_to_success(adapter_instance):
    client = adapter_instance.client
    client.plugins["xep_0444"] = MagicMock()

    source = MagicMock()
    source.chat_id = "user@example.org"
    source.user_id = "user@example.org"

    evt = MagicMock()
    evt.source = source
    evt.message_id = "msg-r1"

    await adapter_instance.on_processing_start(evt)
    client.plugins["xep_0444"].send_reactions.assert_called_with(
        to=adapter.JID("user@example.org"),
        to_id="msg-r1",
        reactions=["👀"],
    )
    assert "msg-r1" in adapter_instance._pending_reactions

    await adapter_instance.on_processing_complete(evt, ProcessingOutcome.SUCCESS)
    calls = client.plugins["xep_0444"].send_reactions.call_args_list
    # First call removes 👀, second sends ✅
    assert calls[-1].kwargs.get("reactions") == ["✅"]
    assert "msg-r1" not in adapter_instance._pending_reactions


@pytest.mark.asyncio
async def test_reaction_lifecycle_failure(adapter_instance):
    client = adapter_instance.client
    client.plugins["xep_0444"] = MagicMock()

    source = MagicMock()
    source.chat_id = "user@example.org"
    source.user_id = "user@example.org"

    evt = MagicMock()
    evt.source = source
    evt.message_id = "msg-r2"

    await adapter_instance.on_processing_start(evt)
    await adapter_instance.on_processing_complete(evt, ProcessingOutcome.FAILURE)
    calls = client.plugins["xep_0444"].send_reactions.call_args_list
    assert calls[-1].kwargs.get("reactions") == ["❌"]


@pytest.mark.asyncio
async def test_reaction_cancelled_sends_no_final(adapter_instance):
    client = adapter_instance.client
    client.plugins["xep_0444"] = MagicMock()

    source = MagicMock()
    source.chat_id = "user@example.org"
    source.user_id = "user@example.org"

    evt = MagicMock()
    evt.source = source
    evt.message_id = "msg-r3"

    await adapter_instance.on_processing_start(evt)
    await adapter_instance.on_processing_complete(evt, ProcessingOutcome.CANCELLED)
    calls = client.plugins["xep_0444"].send_reactions.call_args_list
    # Only 👀 was sent; no final reaction
    assert len(calls) == 1
    assert calls[0].kwargs.get("reactions") == ["👀"]


# -----------------------------------------------------------------
# File upload fallback
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_and_send_without_xep_0363_fails(adapter_instance):
    adapter_instance._registered_plugins.discard("xep_0363")
    result = await adapter_instance._upload_and_send("user@example.org", "/tmp/fake.jpg", None)
    assert result.success is False
    assert "xep-0363" in result.error.lower()


# -----------------------------------------------------------------
# Standalone sender
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_sender_connect_failure():
    cfg = MagicMock()
    cfg.jid = "bot@example.org"
    cfg.password = "bad"
    cfg.home_channel = None
    cfg.fileserver_url = None

    # Patch connect to fail
    with patch.object(adapter.XmppAdapter, "connect", return_value=False):
        with patch.object(adapter.XmppAdapter, "fatal_error_message", return_value="auth failed"):
            result = await adapter.send_xmpp_message(cfg, "user@example.org", "hi")
    assert result["success"] is False
    assert "auth failed" in result["error"]


# -----------------------------------------------------------------
# Typing indicators
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_typing_without_xep_0085_is_silent(adapter_instance):
    adapter_instance._registered_plugins.discard("xep_0085")
    # Should not raise
    await adapter_instance.send_typing("user@example.org")


@pytest.mark.asyncio
async def test_stop_typing_without_xep_0085_is_silent(adapter_instance):
    adapter_instance._registered_plugins.discard("xep_0085")
    await adapter_instance.stop_typing("user@example.org")


# -----------------------------------------------------------------
# Voice fallback when xep_0447 unavailable
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_voice_falls_back_to_upload_when_xep_0447_missing(adapter_instance):
    adapter_instance._registered_plugins.discard("xep_0447")
    with patch.object(adapter_instance, "_upload_and_send", new_callable=AsyncMock) as mock_up:
        mock_up.return_value = adapter.SendResult(success=True, message_id="v1")
        result = await adapter_instance.send_voice("user@example.org", "/tmp/voice.ogg")
    assert result.success is True
    mock_up.assert_awaited_once_with("user@example.org", "/tmp/voice.ogg", caption=None)


# -----------------------------------------------------------------
# Ad-hoc command setup deferred to session start
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_adhoc_setup_without_xep_0050_is_safe(adapter_instance):
    adapter_instance._registered_plugins.discard("xep_0050")
    # Must not raise
    await adapter_instance._setup_adhoc_commands()


@pytest.mark.asyncio
async def test_adhoc_setup_without_client_is_safe():
    cfg = MagicMock()
    cfg.jid = "bot@example.org"
    cfg.password = "secret"
    cfg.home_channel = None
    cfg.fileserver_url = None
    a = adapter.XmppAdapter(cfg)
    a.client = None
    a._registered_plugins = {"xep_0050"}
    await a._setup_adhoc_commands()
