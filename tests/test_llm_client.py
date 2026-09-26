import httpx
import pytest

from app.services.llm_client import GroqLLMClient


@pytest.mark.asyncio
async def test_llm_client_returns_none_when_unconfigured() -> None:
    client = GroqLLMClient(api_key="")
    assert not client.is_configured
    result = await client.reason("Help me diagnose this")
    assert result is None


@pytest.mark.asyncio
async def test_llm_client_strips_whitespace_from_api_key() -> None:
    client = GroqLLMClient(api_key="   gsk_test_key_123   ")
    assert client.is_configured
    assert client.api_key == "gsk_test_key_123"


@pytest.mark.asyncio
async def test_llm_client_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_post(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "The database host is unreachable. Check network routing."
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = GroqLLMClient(api_key="gsk_valid_mock_key")
    result = await client.reason("Diagnose Postgres timeout")
    assert result == "The database host is unreachable. Check network routing."


@pytest.mark.asyncio
async def test_llm_client_handles_http_errors_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_post_401(self, url, **kwargs):
        return httpx.Response(
            status_code=401,
            json={"error": {"message": "Invalid API Key"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_401)

    client = GroqLLMClient(api_key="gsk_invalid_mock_key")
    result = await client.reason("Diagnose Postgres timeout")
    assert result is None


@pytest.mark.asyncio
async def test_llm_client_handles_timeout_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_post_timeout(self, url, **kwargs):
        raise httpx.ReadTimeout("Connection timed out after 10s")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_401 if False else mock_post_timeout)

    client = GroqLLMClient(api_key="gsk_mock_key", timeout=0.001)
    result = await client.reason("Diagnose Postgres timeout")
    assert result is None


@pytest.mark.asyncio
async def test_llm_client_handles_malformed_json_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_post_malformed(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"unexpected_field": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_malformed)

    client = GroqLLMClient(api_key="gsk_mock_key")
    result = await client.reason("Diagnose Postgres timeout")
    assert result is None
