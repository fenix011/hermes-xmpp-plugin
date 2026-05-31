"""Tests for OMEMO encryption support."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

adapter = pytest.importorskip("adapter")


# ------------------------------------------------------------------
# _StorageImpl
# ------------------------------------------------------------------

class TestStorageImpl:
    def test_json_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "omemo.json"
        store = adapter._StorageImpl(path)

        # pylint: disable=protected-access
        assert store._data == {}

        # store a dict value
        value = {"identity_key": "foobar", "device_id": 123}
        # _store is async
        import asyncio

        asyncio.run(store._store("device_info", value))
        assert store._data["device_info"] == value

        # verify it persisted to disk
        with open(path, encoding="utf-8") as f:
            disk = json.load(f)
        assert disk["device_info"] == value

    def test_delete_removes_key(self, tmp_path: Path) -> None:
        path = tmp_path / "omemo.json"
        store = adapter._StorageImpl(path)
        store._data["to_delete"] = "gone"
        # create the file
        store._save()  # type: ignore[attr-defined]

        import asyncio

        asyncio.run(store._delete("to_delete"))
        assert "to_delete" not in store._data
        with open(path, encoding="utf-8") as f:
            assert "to_delete" not in json.load(f)

    def test_load_returns_just_or_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "omemo.json"
        store = adapter._StorageImpl(path)
        store._data["present"] = "value"

        import asyncio

        just = asyncio.run(store._load("present"))
        nothing = asyncio.run(store._load("missing"))

        # slixmpp-omemo uses a Maybe monad: "Maybe" is the module,
        # "Just" and "Nothing" are inside it.
        assert just is not nothing  # different containers


# ------------------------------------------------------------------
# Config helpers
# ------------------------------------------------------------------

class Config:
    def __init__(self, extra=None):
        self.extra = extra or {}


def test_apply_yaml_config_seeds_omemo(monkeypatch):
    for name in ["XMPP_JID", "XMPP_PASSWORD", "XMPP_OMEMO_ENABLED", "XMPP_OMEMO_STORAGE_PATH"]:
        monkeypatch.delenv(name, raising=False)

    extra = adapter._apply_yaml_config(
        {},
        {
            "jid": "bot@example.org",
            "password": "secret",
            "omemo_enabled": True,
            "omemo_storage_path": "/tmp/omemo_store.json",
        },
    )

    assert extra["omemo"] == {
        "enabled": True,
        "storage_path": "/tmp/omemo_store.json",
    }
    assert os.environ["XMPP_JID"] == "bot@example.org"
    # omemo env vars are optional and not auto-exported by _apply_yaml_config,
    # but the adapter install flow does set them. This test verifies extra dict shape.


# ------------------------------------------------------------------
# Plugin registration shape — OMEMO fields are not part of the core
# register_platform() kwargs (they live in plugin.yaml as optional_env).
# They surface through _apply_yaml_config into the extra dict.
# ------------------------------------------------------------------


def test_omemo_values_surface_in_extra():
    """The _apply_yaml_config helper wires omemo_enabled and
    omemo_storage_path into the extra dict under the 'omemo' key."""
    extra = adapter._apply_yaml_config(
        {},
        {
            "jid": "bot@example.org",
            "password": "secret",
            "omemo_enabled": True,
            "omemo_storage_path": "/tmp/omemo.json",
        },
    )
    assert extra.get("omemo") == {"enabled": True, "storage_path": "/tmp/omemo.json"}
