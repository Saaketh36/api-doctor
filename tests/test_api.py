import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_doctor
from app.services.api_doctor import APIDoctor


class MockLLMClient:
    async def reason(self, prompt: str) -> str | None:
        return "Deterministic test mock reasoning"


@pytest.fixture(autouse=True)
def override_doctor():
    doctor = APIDoctor(llm_client=MockLLMClient())
    app.dependency_overrides[get_doctor] = lambda: doctor
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_diagnose_endpoint_valid_request() -> None:
    payload = {
        "endpoint": "POST /users",
        "error_message": "500 database connection timeout",
        "logs": "psycopg2.OperationalError: could not connect to server: Connection timed out",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/diagnose", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "postgres_connection_timeout"
        assert data["confidence"] >= 0.8
        assert isinstance(data["fixes"], list)
        assert isinstance(data["debugging_steps"], list)
        assert "tool_results" in data


@pytest.mark.asyncio
async def test_diagnose_endpoint_empty_fields_validation_error() -> None:
    # Empty strings should fail validation
    payload = {
        "endpoint": "   ",
        "error_message": "",
        "logs": "",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/diagnose", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_diagnose_endpoint_missing_fields() -> None:
    payload = {
        "endpoint": "POST /orders",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/diagnose", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_diagnose_endpoint_with_code_root() -> None:
    payload = {
        "endpoint": "GET /api/v1/health",
        "error_message": "500 Connection Refused",
        "logs": "psycopg2.OperationalError: could not connect to server: Connection refused",
        "code_root": "non_existent_folder",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/diagnose", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "postgres_connection_refused"
        assert data["tool_results"]["code_references"] == []
