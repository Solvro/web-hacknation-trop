"""Store selection (mock fixtures vs real DB/Redis)."""
from __future__ import annotations

import os

_store = None


def set_store(s) -> None:
    global _store
    _store = s


def get_store():
    global _store
    if _store is None:
        _store = make_store(current_mode())
    return _store


def current_mode() -> str:
    from trop.config import settings
    return (os.environ.get("TROP_MODE") or settings.trop_mode or "live").lower()


def make_store(mode: str):
    if mode == "mock":
        from trop.api.mockstore import MockStore
        return MockStore()
    from trop.api.realstore import RealStore
    return RealStore()
