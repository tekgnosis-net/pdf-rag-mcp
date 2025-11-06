from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.api import create_api  # noqa: E402


def test_health_endpoint():
    """Smoke test: ensure the health endpoint responds successfully."""
    app = create_api()
    client = TestClient(app)

    resp = client.get("/api/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("status") == "ok"
    assert isinstance(payload.get("version"), str)
