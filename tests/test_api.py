from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_register_and_login() -> None:
    client = TestClient(app)
    payload = {"email": f"{uuid4().hex}@example.com", "password": "StrongPass123!", "name": "Test User"}
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_duplicate_registration_is_rejected_case_insensitively() -> None:
    client = TestClient(app)
    first_payload = {"email": "Case@Test.com", "password": "StrongPass123!", "name": "Test User"}
    second_payload = {"email": "case@test.com", "password": "StrongPass123!", "name": "Test User"}

    first_register = client.post("/auth/register", json=first_payload)
    second_register = client.post("/auth/register", json=second_payload)

    assert first_register.status_code == 201
    assert second_register.status_code == 400
