import os

os.environ["TROP_MODE"] = "mock"
os.environ["TROP_MOCK_SPEED"] = "200"

import pytest
from fastapi.testclient import TestClient

from trop.config import settings


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    settings.artifact_dir = tmp_path_factory.mktemp("artifacts")
    os.environ["REPLAY_DIR"] = str(tmp_path_factory.mktemp("replay"))
    from trop.api.app import create_app
    with TestClient(create_app("mock")) as c:
        yield c
