import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
SAMPLE_PATH = Path(__file__).parent.parent / "sample_data" / "marks_sheet_1.webp"

FAKE_EXTRACTION = {
    "candidate": {
        "name": {"value": "Test Candidate", "confidence": 0.95},
        "roll_no": {"value": "12345", "confidence": 0.95},
        "board_or_university": {"value": "Test Board", "confidence": 0.95},
    },
    "subjects": [],
    "result": {},
    "document_confidence": 0.0,
    "warnings": [],
}


def _login() -> str:
    response = client.post("/token", json={"username": settings.auth_username, "password": settings.auth_password})
    return response.json()["access_token"]


def test_health_check():
    assert client.get("/health").status_code == 200


def test_login_rejects_wrong_password():
    response = client.post("/token", json={"username": settings.auth_username, "password": "wrong"})
    assert response.status_code == 401


def test_login_succeeds_with_correct_credentials():
    response = client.post("/token", json={"username": settings.auth_username, "password": settings.auth_password})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_extract_requires_authentication():
    response = client.post("/extract", files={"file": ("marksheet.webp", SAMPLE_PATH.read_bytes(), "image/webp")})
    assert response.status_code == 401


def test_extract_rejects_unsupported_format():
    token = _login()
    response = client.post(
        "/extract",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.zip", b"fake zip content", "application/zip")},
    )
    assert response.status_code == 415


def test_extract_succeeds_with_mocked_llm(monkeypatch):
    async def fake_call(images, prompt):
        return json.dumps(FAKE_EXTRACTION)

    monkeypatch.setattr("app.services.llm_client.call_scout", fake_call)
    monkeypatch.setattr("app.services.llm_client.call_minimax", fake_call)

    token = _login()
    response = client.post(
        "/extract",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("marksheet.webp", SAMPLE_PATH.read_bytes(), "image/webp")},
    )

    assert response.status_code == 200
    assert response.json()["candidate"]["name"]["value"] == "Test Candidate"