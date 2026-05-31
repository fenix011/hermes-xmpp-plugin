from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_plugin_module():
    ns = types.ModuleType("hermes_plugins")
    ns.__path__ = []
    ns.__package__ = "hermes_plugins"
    sys.modules["hermes_plugins"] = ns
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.hermes_xmpp_plugin",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "hermes_plugins.hermes_xmpp_plugin"
    mod.__path__ = [str(ROOT)]
    sys.modules["hermes_plugins.hermes_xmpp_plugin"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class FakeContext:
    def __init__(self):
        self.calls = []

    def register_platform(self, **kwargs):
        self.calls.append(kwargs)


def test_user_plugin_loader_shape_registers_platform():
    mod = load_plugin_module()
    ctx = FakeContext()
    mod.register(ctx)
    assert len(ctx.calls) == 1
    entry = ctx.calls[0]
    assert entry["name"] == "xmpp"
    assert entry["label"] == "XMPP/Jabber"
    assert entry["required_env"] == ["XMPP_JID", "XMPP_PASSWORD"]
    assert entry["cron_deliver_env_var"] == "XMPP_HOME_CHANNEL"
    assert entry["allowed_users_env"] == "XMPP_ALLOWED_USERS"
    assert callable(entry["adapter_factory"])
    assert callable(entry["standalone_sender_fn"])
    assert callable(entry["apply_yaml_config_fn"])
