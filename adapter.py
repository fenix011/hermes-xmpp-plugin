"""XMPP (Jabber) platform adapter.

Built on slixmpp. Connects to any XMPP server, supports 1:1 chats and MUC
groupchat, and uses XEP-0363 (HTTP File Upload) for attachments.

Encryption posture (ADR-0002): TLS-to-server only. OMEMO is deferred to a
follow-up extra (`hermes-agent[xmpp-omemo]`). Adapter logs a startup warning
to make this explicit.

Packaged as a third-party Hermes platform plugin.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import slixmpp

    SLIXMPP_AVAILABLE = True
except ImportError:
    SLIXMPP_AVAILABLE = False
    slixmpp = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)


def check_xmpp_requirements() -> bool:
    """Confirm the [xmpp] extra is installed.

    Lazy-installs slixmpp via ``tools.lazy_deps.ensure("platform.xmpp")``
    on first call if not present.
    """
    global SLIXMPP_AVAILABLE, slixmpp
    if not SLIXMPP_AVAILABLE:
        try:
            from tools.lazy_deps import ensure as _lazy_ensure
            _lazy_ensure("platform.xmpp", prompt=False)
        except Exception:
            return False
        try:
            import slixmpp as _slixmpp
        except ImportError:
            return False
        slixmpp = _slixmpp
        SLIXMPP_AVAILABLE = True
    return True


@dataclass
class _MucRoom:
    """A configured MUC room the adapter joins on connect."""
    room: str           # bare room JID, e.g. "team@conference.example.org"
    nick: Optional[str] = None  # optional override; falls back to muc_nick


def _parse_muc_rooms(value: str, default_nick: Optional[str]) -> List[_MucRoom]:
    rooms: List[_MucRoom] = []
    for entry in (value or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "/" in entry:
            room, _, nick = entry.partition("/")
            rooms.append(_MucRoom(room=room.strip(), nick=nick.strip() or default_nick))
        else:
            rooms.append(_MucRoom(room=entry, nick=default_nick))
    return rooms


class XmppAdapter(BasePlatformAdapter):
    """slixmpp-backed adapter satisfying BasePlatformAdapter.

    The slixmpp client is constructed lazily in ``connect()``; ``__init__``
    only parses config so unit tests can introspect adapter state without
    paying the slixmpp import / event-loop cost.
    """

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("xmpp"))
        extra = config.extra or {}

        self.jid: str = str(extra.get("jid") or os.getenv("XMPP_JID", ""))
        self._password: str = str(extra.get("password") or os.getenv("XMPP_PASSWORD", ""))
        self.host: Optional[str] = extra.get("host") or os.getenv("XMPP_HOST") or None
        self.port: int = int(extra.get("port") or os.getenv("XMPP_PORT", 5222))
        self.muc_nick: str = extra.get("muc_nick") or os.getenv("XMPP_MUC_NICK") or self._default_nick()
        self.muc_rooms: List[_MucRoom] = _parse_muc_rooms(
            str(extra.get("muc_rooms") or os.getenv("XMPP_MUC_ROOMS", "")), self.muc_nick
        )

        # Allow-list: bare JIDs the bot will accept inbound from.
        allow_all_raw = str(extra.get("allow_all_users", os.getenv("XMPP_ALLOW_ALL_USERS", "")))
        self.allow_all_users: bool = allow_all_raw.strip().lower() in ("1", "true", "yes")
        allowed_env = str(extra.get("allowed_users") or os.getenv("XMPP_ALLOWED_USERS", "")).strip()
        self.allowed_users = {
            j.strip() for j in allowed_env.split(",") if j.strip()
        }

        # Lazily created in connect()
        self.client: Optional[Any] = None
        self._process_task: Optional[asyncio.Task] = None
        self._session_ready: Optional[asyncio.Event] = None
        self._self_bare = self._bare(self.jid)

        # Set of bare room JIDs we've configured for groupchat send routing.
        self._known_mucs = {r.room for r in self.muc_rooms}

        # Track which optional plugins registered successfully so feature
        # methods (chat states, HTTP upload) can no-op gracefully if a plugin
        # is missing instead of raising TypeError on unknown kwargs.
        self._registered_plugins: set[str] = set()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    async def connect(self) -> bool:
        client = slixmpp.ClientXMPP(self.jid, self._password)
        # Plugins we need: chat states, MUC, HTTP File Upload, OOB, disco, ping.
        for plugin in ("xep_0030", "xep_0045", "xep_0066", "xep_0085", "xep_0199",
                       "xep_0363"):
            try:
                client.register_plugin(plugin)
                self._registered_plugins.add(plugin)
            except Exception:
                logger.warning("xmpp: failed to register slixmpp plugin %s", plugin)

        # ADR-0001 §5: enforce TLS, refuse plaintext.
        client.use_starttls = True
        client.force_starttls = True

        client.add_event_handler("session_start", self._on_session_start)
        client.add_event_handler("message", self._on_message)
        client.add_event_handler("groupchat_message", self._on_message)
        client.add_event_handler("disconnected", self._on_disconnected)
        client.add_event_handler("failed_auth", self._on_failed_auth)

        self.client = client
        self._session_ready = asyncio.Event()

        connect_kwargs: Dict[str, Any] = {}
        if self.host:
            connect_kwargs["address"] = (self.host, self.port)

        try:
            ok = client.connect(**connect_kwargs)
        except TypeError:
            # Older slixmpp signature
            ok = client.connect()
        if ok is False:
            self._set_fatal_error(
                "xmpp_connect_failed", "XMPP connect() returned False", retryable=True
            )
            return False

        loop = asyncio.get_event_loop()
        self._process_task = loop.create_task(self._run_process())

        logger.warning(
            "XMPP adapter is running without OMEMO. Messages are encrypted in "
            "transit (TLS) but visible to your XMPP server operator."
        )
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                logger.exception("xmpp: error during disconnect()")
        if self._process_task is not None:
            self._process_task.cancel()
            self._process_task = None
        self.client = None
        self._mark_disconnected()

    async def _run_process(self) -> None:
        """slixmpp's process loop runs in the existing asyncio loop."""
        try:
            await self.client.disconnected
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("xmpp: process loop crashed")

    async def _on_session_start(self, _event: Any) -> None:
        self.client.send_presence()
        try:
            await self.client.get_roster()
        except Exception:
            logger.exception("xmpp: get_roster failed")
        for room in self.muc_rooms:
            try:
                self.client.plugin["xep_0045"].join_muc(room.room, room.nick or self.muc_nick)
            except Exception:
                logger.exception("xmpp: failed to join MUC %s", room.room)
        if self._session_ready is not None:
            self._session_ready.set()

    async def _on_disconnected(self, _event: Any) -> None:
        self._mark_disconnected()

    async def _on_failed_auth(self, _event: Any) -> None:
        self._set_fatal_error(
            "xmpp_auth_failed",
            "XMPP authentication failed — check XMPP_JID/XMPP_PASSWORD",
            retryable=False,
        )

    # -----------------------------------------------------------------
    # Inbound
    # -----------------------------------------------------------------

    async def _on_message(self, stanza: Any) -> None:
        """Convert a slixmpp Message stanza into a MessageEvent and dispatch."""
        try:
            stanza_type = stanza["type"]
            if stanza_type in ("error", "headline"):
                return
            if stanza_type not in ("chat", "groupchat", "normal"):
                return

            from_jid = stanza.get_from()
            from_full = str(from_jid)
            from_bare = getattr(from_jid, "bare", None) or self._bare(from_full)
            from_resource = getattr(from_jid, "resource", "") or ""

            # Filter our own echoes (especially common in MUC).
            if from_bare == self._self_bare:
                return

            body = stanza["body"] or ""
            if not body:
                return

            if stanza_type == "groupchat":
                chat_type = "group"
                chat_id = from_bare  # room JID
                user_name = from_resource or None  # MUC nick lives in the resource
                user_id = self._muc_real_jid(stanza) or chat_id
            else:
                chat_type = "dm"
                chat_id = from_bare
                user_name = None
                user_id = from_bare

            if not self._is_authorized(chat_type=chat_type, chat_id=chat_id, user_jid=user_id):
                logger.debug(
                    "xmpp: dropping unauthorized %s from %s in %s",
                    chat_type, user_id, chat_id,
                )
                return

            source = self.build_source(
                chat_id=chat_id,
                chat_type=chat_type,
                user_id=user_id,
                user_name=user_name,
            )
            event = MessageEvent(
                text=body,
                message_type=MessageType.TEXT,
                source=source,
                raw_message=stanza,
                message_id=stanza.get("id") or None,
            )
            await self.handle_message(event)
        except Exception:
            logger.exception("xmpp: error handling inbound stanza")

    def _muc_real_jid(self, stanza: Any) -> Optional[str]:
        """Best-effort extraction of the MUC sender's real bare JID.

        Only returned when the room exposes occupants' real JIDs (semi-anon
        or non-anon rooms). For fully anonymous rooms this is unavailable
        and we fall back to the room JID for authorization.
        """
        try:
            muc = stanza.get("muc")
            if muc and getattr(muc, "jid", None):
                return self._bare(str(muc["jid"]))
        except Exception:
            pass
        return None

    def _is_authorized(self, *, chat_type: str, chat_id: str, user_jid: str) -> bool:
        if self.allow_all_users:
            return True
        if chat_type == "group":
            # MUC presence is gated by room membership: the bot operator opts
            # into a room by configuring it in XMPP_MUC_ROOMS. Anonymous and
            # semi-anonymous rooms hide participants' real JIDs from the
            # bot, so per-user filtering is structurally impossible — the
            # room itself is the access boundary.
            return chat_id in self._known_mucs
        if not self.allowed_users:
            # Empty allow-list AND no allow-all flag → reject by default.
            # This matches the security posture of the Signal / WhatsApp
            # adapters: misconfiguration must not silently accept the world.
            return False
        return self._bare(user_jid) in self.allowed_users

    # -----------------------------------------------------------------
    # Outbound
    # -----------------------------------------------------------------

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        if self.client is None:
            return SendResult(success=False, error="xmpp not connected", retryable=True)
        mtype = "groupchat" if self._is_muc(chat_id) else "chat"
        try:
            stanza = self.client.send_message(
                mto=chat_id,
                mbody=content,
                mtype=mtype,
            )
            msg_id = None
            try:
                msg_id = stanza["id"]
            except Exception:
                pass
            return SendResult(success=True, message_id=msg_id, raw_response=stanza)
        except Exception as exc:
            logger.exception("xmpp: send failed")
            return SendResult(success=False, error=str(exc), retryable=True)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        if self.client is None or "xep_0085" not in self._registered_plugins:
            return
        mtype = "groupchat" if self._is_muc(chat_id) else "chat"
        try:
            self.client.send_message(mto=chat_id, mtype=mtype, mchat_state="composing")
        except Exception:
            logger.debug("xmpp: send_typing failed", exc_info=True)

    async def stop_typing(self, chat_id: str) -> None:
        if self.client is None or "xep_0085" not in self._registered_plugins:
            return
        mtype = "groupchat" if self._is_muc(chat_id) else "chat"
        try:
            self.client.send_message(mto=chat_id, mtype=mtype, mchat_state="active")
        except Exception:
            logger.debug("xmpp: stop_typing failed", exc_info=True)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._upload_and_send(chat_id, image_path, caption)

    async def send_document(
        self,
        chat_id: str,
        path: str,
        caption: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._upload_and_send(chat_id, path, caption)

    async def send_voice(
        self,
        chat_id: str,
        path: str,
        **kwargs,
    ) -> SendResult:
        return await self._upload_and_send(chat_id, path, caption=None)

    async def send_video(
        self,
        chat_id: str,
        path: str,
        caption: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._upload_and_send(chat_id, path, caption)

    async def _upload_and_send(
        self, chat_id: str, path: str, caption: Optional[str]
    ) -> SendResult:
        """XEP-0363 HTTP File Upload + body containing the GET URL.

        Receiving clients (Conversations, Dino, Gajim) render the URL inline
        as a media bubble. We also include a XEP-0066 OOB hint via metadata
        when available.
        """
        if self.client is None:
            return SendResult(success=False, error="xmpp not connected", retryable=True)
        if "xep_0363" not in self._registered_plugins:
            return SendResult(
                success=False,
                error="xmpp HTTP File Upload (XEP-0363) not available",
                retryable=False,
            )
        # Pass content-type so the receiving server's slot grant carries an
        # accurate Content-Type. Some clients render media inline based on it
        # rather than the URL extension.
        content_type, _ = mimetypes.guess_type(path)
        upload_kwargs: Dict[str, Any] = {
            "filename": Path(path).name,
            "input_file": path,
        }
        if content_type:
            upload_kwargs["content_type"] = content_type
        try:
            upload = self.client["xep_0363"].upload_file
            try:
                url = await upload(**upload_kwargs)
            except TypeError:
                # Older slixmpp signatures don't accept content_type kwarg.
                upload_kwargs.pop("content_type", None)
                url = await upload(**upload_kwargs)
        except Exception as exc:
            logger.exception("xmpp: HTTP upload (XEP-0363) failed")
            return SendResult(success=False, error=str(exc), retryable=True)

        body = url if not caption else f"{caption}\n{url}"
        mtype = "groupchat" if self._is_muc(chat_id) else "chat"
        try:
            stanza = self.client.send_message(mto=chat_id, mbody=body, mtype=mtype)
            msg_id = None
            try:
                msg_id = stanza["id"]
            except Exception:
                pass
            return SendResult(success=True, message_id=msg_id, raw_response=stanza)
        except Exception as exc:
            return SendResult(success=False, error=str(exc), retryable=True)

    # -----------------------------------------------------------------
    # Misc
    # -----------------------------------------------------------------

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        chat_type = "group" if self._is_muc(chat_id) else "dm"
        return {"chat_id": chat_id, "type": chat_type, "name": chat_id}

    # Common MUC subdomain conventions across major XMPP servers. Operators
    # using a non-standard prefix should set XMPP_MUC_ROOMS, which takes
    # precedence over the heuristic.
    _MUC_DOMAIN_PREFIXES = ("conference.", "muc.", "rooms.", "chat.", "groups.")

    def _is_muc(self, chat_id: str) -> bool:
        if chat_id in self._known_mucs:
            return True
        domain = chat_id.split("@", 1)[-1]
        return any(domain.startswith(p) for p in self._MUC_DOMAIN_PREFIXES)

    @staticmethod
    def _bare(jid: str) -> str:
        return jid.split("/", 1)[0] if "/" in jid else jid

    @staticmethod
    def _default_nick() -> str:
        return "hermes"


# ---------------------------------------------------------------------
# Standalone helper for cron / send_message_tool — sends a single message
# without spinning up the full adapter inside the gateway process.
# ---------------------------------------------------------------------

async def send_xmpp_message(
    pconfig: PlatformConfig,
    chat_id: str,
    message: str,
    *,
    thread_id: str | None = None,
    media_files: list[str] | None = None,
    force_document: bool = False,
) -> Dict[str, Any]:
    """One-shot send used by cron jobs and the send_message tool.

    Connects, sends, disconnects. Heavy for chat use, but the right shape
    for "send this single notification" callers that don't have access to
    a running gateway adapter instance.
    """
    adapter = XmppAdapter(pconfig)
    if not check_xmpp_requirements():
        return {"success": False, "error": "slixmpp not installed"}
    try:
        ok = await adapter.connect()
        if not ok:
            return {"success": False, "error": adapter.fatal_error_message() or "connect failed"}
        # Wait for session_start (and any MUC joins) to complete, with a
        # bounded timeout so a slow/unresponsive server can't hang cron jobs.
        if adapter._session_ready is not None:
            try:
                await asyncio.wait_for(adapter._session_ready.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("xmpp: session_start did not fire within 10s; sending anyway")
        last_result = None
        if message:
            last_result = await adapter.send(chat_id=chat_id, content=message)
            if not last_result.success:
                return {"success": False, "error": last_result.error}
        for media_path in media_files or []:
            last_result = await adapter.send_document(chat_id=chat_id, path=media_path)
            if not last_result.success:
                return {"success": False, "error": last_result.error}
        return {
            "success": True,
            "platform": "xmpp",
            "chat_id": chat_id,
            "message_id": getattr(last_result, "message_id", None),
        }
    finally:
        await adapter.disconnect()


# ---------------------------------------------------------------------
# Platform plugin registration hooks
# ---------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _csv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def _env_enablement() -> Optional[dict[str, Any]]:
    """Seed PlatformConfig.extra from env-only setups."""
    jid = os.getenv("XMPP_JID", "").strip()
    password = os.getenv("XMPP_PASSWORD", "").strip()
    if not (jid and password):
        return None
    data: dict[str, Any] = {"jid": jid, "password": password}
    for env, key in (
        ("XMPP_HOST", "host"),
        ("XMPP_PORT", "port"),
        ("XMPP_MUC_ROOMS", "muc_rooms"),
        ("XMPP_MUC_NICK", "muc_nick"),
        ("XMPP_ALLOWED_USERS", "allowed_users"),
        ("XMPP_ALLOW_ALL_USERS", "allow_all_users"),
    ):
        value = os.getenv(env, "").strip()
        if value:
            data[key] = value
    return data


def _apply_yaml_config(yaml_cfg: dict, xmpp_cfg: dict) -> Optional[dict[str, Any]]:
    """Translate config.yaml XMPP blocks into PlatformConfig.extra and env.

    Supports either:

        xmpp:
          enabled: true
          jid: hermes@example.org
          password: ${XMPP_PASSWORD}

    or:

        platforms:
          xmpp:
            enabled: true
            extra:
              jid: hermes@example.org

    Env vars still win when already present.
    """
    raw = dict(xmpp_cfg or {})
    extra = dict(raw.get("extra") or {})
    for key in (
        "jid", "password", "host", "port", "muc_rooms", "muc_nick",
        "allowed_users", "allow_all_users",
    ):
        if key in raw and key not in extra:
            extra[key] = raw[key]

    env_map = {
        "jid": "XMPP_JID",
        "password": "XMPP_PASSWORD",
        "host": "XMPP_HOST",
        "port": "XMPP_PORT",
        "muc_rooms": "XMPP_MUC_ROOMS",
        "muc_nick": "XMPP_MUC_NICK",
        "allowed_users": "XMPP_ALLOWED_USERS",
        "allow_all_users": "XMPP_ALLOW_ALL_USERS",
        "home_channel": "XMPP_HOME_CHANNEL",
    }
    for key, env in env_map.items():
        value = raw.get(key, extra.get(key))
        if key == "home_channel" and isinstance(value, dict):
            value = value.get("chat_id")
        if value is None or os.getenv(env):
            continue
        os.environ[env] = _csv(value)

    return extra or None


def validate_config(config: PlatformConfig) -> bool:
    extra = getattr(config, "extra", {}) or {}
    return bool((extra.get("jid") or os.getenv("XMPP_JID")) and (extra.get("password") or os.getenv("XMPP_PASSWORD")))


def is_connected(config: PlatformConfig) -> bool:
    return validate_config(config)


def _build_adapter(config: PlatformConfig) -> XmppAdapter:
    return XmppAdapter(config)


def register(ctx) -> None:
    """Hermes plugin entry point."""
    ctx.register_platform(
        name="xmpp",
        label="XMPP/Jabber",
        adapter_factory=_build_adapter,
        check_fn=check_xmpp_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["XMPP_JID", "XMPP_PASSWORD"],
        install_hint="Install dependencies with: uv pip install slixmpp==1.15.0 aiohttp==3.13.4",
        env_enablement_fn=_env_enablement,
        apply_yaml_config_fn=_apply_yaml_config,
        cron_deliver_env_var="XMPP_HOME_CHANNEL",
        standalone_sender_fn=send_xmpp_message,
        allowed_users_env="XMPP_ALLOWED_USERS",
        allow_all_env="XMPP_ALLOW_ALL_USERS",
        max_message_length=10000,
        emoji="💬",
        pii_safe=False,
        allow_update_command=True,
        platform_hint=(
            "You are communicating over XMPP/Jabber. Use plain text by default. "
            "XMPP clients vary in markdown rendering, so avoid heavy markdown tables. "
            "Keep replies reasonably concise unless the user asks for detail."
        ),
    )
