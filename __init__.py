"""Hermes XMPP/Jabber platform plugin."""

# Keep imports lazy for Hermes' user-plugin loader. Importing adapter.py at
# module scope can trip circular initialization during spec.loader.exec_module().
def register(ctx):
    from .adapter import register as _register
    return _register(ctx)

__all__ = ["register"]
