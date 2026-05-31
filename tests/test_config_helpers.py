from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import adapter  # noqa: E402


class Config:
    def __init__(self, extra=None):
        self.extra = extra or {}


def test_parse_muc_rooms_with_optional_nick():
    rooms = adapter._parse_muc_rooms("a@conference.example/herm,b@muc.example", "bot")
    assert [(r.room, r.nick) for r in rooms] == [
        ("a@conference.example", "herm"),
        ("b@muc.example", "bot"),
    ]


def test_apply_yaml_config_seeds_extra_and_env(monkeypatch):
    for name in [
        "XMPP_JID", "XMPP_PASSWORD", "XMPP_ALLOWED_USERS", "XMPP_HOME_CHANNEL"
    ]:
        monkeypatch.delenv(name, raising=False)
    extra = adapter._apply_yaml_config({}, {
        "jid": "bot@example.org",
        "password": "secret",
        "allowed_users": ["sam@example.org", "mom@example.org"],
        "home_channel": "sam@example.org",
    })
    assert extra["jid"] == "bot@example.org"
    assert os.environ["XMPP_JID"] == "bot@example.org"
    assert os.environ["XMPP_ALLOWED_USERS"] == "sam@example.org,mom@example.org"
    assert os.environ["XMPP_HOME_CHANNEL"] == "sam@example.org"


def test_validate_config_accepts_extra_without_env(monkeypatch):
    monkeypatch.delenv("XMPP_JID", raising=False)
    monkeypatch.delenv("XMPP_PASSWORD", raising=False)
    assert adapter.validate_config(Config({"jid": "bot@example.org", "password": "pw"}))
    assert not adapter.validate_config(Config({"jid": "bot@example.org"}))
