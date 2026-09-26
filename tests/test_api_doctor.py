import pytest

from app.models.diagnosis import CodeReference, DiagnosisRequest
from app.services.api_doctor import APIDoctor


class NullLLMClient:
    async def reason(self, prompt: str) -> None:
        return None


class MockLLMClient:
    async def reason(self, prompt: str) -> str:
        return "The database credentials in production have expired. Please rotate secrets."


class MockCodeSearcher:
    def search(self, root: str | None, endpoint: str, terms=None) -> list[CodeReference]:
        if not root:
            return []
        return [
            CodeReference(path="src/database.py", line=12, snippet="DATABASE_URL = get_secret('DB_URL')")
        ]


@pytest.mark.asyncio
async def test_api_doctor_returns_structured_timeout_diagnosis() -> None:
    doctor = APIDoctor(llm_client=NullLLMClient())
    request = DiagnosisRequest(
        endpoint="POST /users",
        error_message="500 database connection timeout",
        logs="psycopg2.OperationalError: could not connect to server: Connection timed out",
    )

    diagnosis = await doctor.diagnose(request)

    assert diagnosis.category == "postgres_connection_timeout"
    assert diagnosis.confidence >= 0.8
    assert len(diagnosis.fixes) >= 2
    assert len(diagnosis.debugging_steps) >= 3
    assert diagnosis.tool_results.log_facts


@pytest.mark.asyncio
async def test_api_doctor_diagnoses_all_postgres_categories() -> None:
    doctor = APIDoctor(llm_client=NullLLMClient())
    categories_and_logs = [
        ("postgres_connection_refused", "psycopg2.OperationalError: could not connect to server: Connection refused"),
        ("postgres_authentication_failed", 'FATAL: password authentication failed for user "api_user"'),
        ("postgres_database_missing", 'FATAL: database "non_existent_db" does not exist'),
        ("postgres_host_resolution_failed", "psycopg2.OperationalError: could not translate host name \"invalid.db.internal\""),
        ("postgres_too_many_connections", "FATAL: sorry, too many clients already"),
        ("postgres_ssl_error", "psycopg2.OperationalError: SSL error: certificate verify failed"),
    ]

    for expected_cat, log_text in categories_and_logs:
        request = DiagnosisRequest(
            endpoint="GET /items",
            error_message="500 Database Error",
            logs=log_text,
        )
        diagnosis = await doctor.diagnose(request)
        assert diagnosis.category == expected_cat
        assert diagnosis.confidence >= 0.8
        assert diagnosis.fixes
        assert diagnosis.debugging_steps


@pytest.mark.asyncio
async def test_api_doctor_unknown_error_fallback() -> None:
    doctor = APIDoctor(llm_client=NullLLMClient())
    request = DiagnosisRequest(
        endpoint="GET /healthz",
        error_message="502 Bad Gateway",
        logs="Some arbitrary non-database error message",
    )

    diagnosis = await doctor.diagnose(request)

    assert diagnosis.category == "unknown"
    assert diagnosis.confidence == 0.25
    assert "No known PostgreSQL error pattern" in diagnosis.root_cause
    assert diagnosis.fixes
    assert diagnosis.debugging_steps


@pytest.mark.asyncio
async def test_api_doctor_integrates_code_searcher_and_llm() -> None:
    doctor = APIDoctor(
        code_searcher=MockCodeSearcher(),
        llm_client=MockLLMClient(),
    )
    request = DiagnosisRequest(
        endpoint="POST /payments",
        error_message="500 Authentication Failed",
        logs='FATAL: password authentication failed for user "payments_service"',
        code_root="sample/path",
    )

    diagnosis = await doctor.diagnose(request)

    assert diagnosis.category == "postgres_authentication_failed"
    assert len(diagnosis.tool_results.code_references) == 1
    assert diagnosis.tool_results.code_references[0].path == "src/database.py"

    sources = [e.source for e in diagnosis.evidence]
    assert "log_analyzer" in sources
    assert "code_searcher" in sources
    assert "groq_llm" in sources

    llm_ev = next(e for e in diagnosis.evidence if e.source == "groq_llm")
    assert "rotate secrets" in llm_ev.detail


