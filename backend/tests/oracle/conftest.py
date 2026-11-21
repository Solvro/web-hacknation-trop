import pytest

from trop.config import settings


@pytest.fixture()
def tmp_trop(tmp_path, monkeypatch):
    """Isolated data/cache dirs + offline mode: tests never touch the network or the real cache."""
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "trop_mode", "offline")
    (tmp_path / "data").mkdir()
    return tmp_path
