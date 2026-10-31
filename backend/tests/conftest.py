import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pw_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DEMO_MODE"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["MONITORING_ENABLED"] = "false"
for k in ("COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET", "GEE_PROJECT_ID", "LEVIR_CD_MODEL_PATH", "ROOFTOP_MODEL_PATH"):
    os.environ[k] = ""
os.environ["MODELS_DIR"] = f"{_TMP}/models"

import io
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

CREDS = {
    "admin": ("admin@propertywatch.ai", "AdminPass123!"),
    "reviewer": ("reviewer@propertywatch.ai", "ReviewerPass123!"),
    "owner": ("owner@propertywatch.ai", "OwnerPass123!"),
    "decision": ("decisionmaker@propertywatch.ai", "DecisionPass123!"),
}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    out = {}
    for role, (email, pw) in CREDS.items():
        r = client.post("/api/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, r.text
        out[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return out


@pytest.fixture()
def live_mode():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = False
    yield
    settings.DEMO_MODE = prev


def png_bytes(color=(90, 140, 90), size=64, noise=False):
    img = np.full((size, size, 3), color, dtype=np.uint8)
    if noise:
        img = np.clip(img + np.random.randint(-30, 30, img.shape), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()
