from app.tools.log_analyzer import LogAnalyzer


def test_detects_postgres_connection_timeout() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 database error",
        "psycopg2.OperationalError: could not connect to server: Connection timed out\nIs the server running on host 10.0.0.1?",
    )
    assert facts
    assert any(f["category"] == "postgres_connection_timeout" for f in facts)


def test_detects_postgres_connection_refused() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 internal server error",
        "psycopg2.OperationalError: could not connect to server: Connection refused\nIs the server running on host 'localhost' (127.0.0.1) and accepting TCP/IP connections on port 5432?",
    )
    assert facts
    assert any(f["category"] == "postgres_connection_refused" for f in facts)


def test_detects_authentication_failure() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "Internal Server Error",
        'FATAL: password authentication failed for user "api_user"',
    )
    assert facts
    assert any(f["category"] == "postgres_authentication_failed" for f in facts)


def test_detects_missing_database() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 Database Error",
        'FATAL: database "customers_prod" does not exist',
    )
    assert facts
    assert any(f["category"] == "postgres_database_missing" for f in facts)


def test_detects_host_resolution_failure() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 Internal Server Error",
        "psycopg2.OperationalError: could not translate host name \"db.internal\" to address: Name or service not known",
    )
    assert facts
    assert any(f["category"] == "postgres_host_resolution_failed" for f in facts)


def test_detects_too_many_connections() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 Database Pool Error",
        "FATAL: sorry, too many clients already\nsqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out",
    )
    assert facts
    categories = [f["category"] for f in facts]
    assert "postgres_too_many_connections" in categories


def test_detects_ssl_error() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "500 SSL Handshake Error",
        "psycopg2.OperationalError: SSL error: certificate verify failed (sslmode=verify-full)",
    )
    assert facts
    assert any(f["category"] == "postgres_ssl_error" for f in facts)


def test_unknown_log_returns_empty_facts() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "400 Bad Request",
        "ValueError: invalid literal for int() with base 10: 'abc'",
    )
    assert facts == []


def test_deduplicates_repeated_log_matches() -> None:
    analyzer = LogAnalyzer()
    facts = analyzer.analyze(
        "connection timed out",
        "Line 1: connection timed out\nLine 2: connection timed out\nLine 3: connection timed out",
    )
    # Deduplication should collapse identical category + matched text
    timeout_facts = [f for f in facts if f["category"] == "postgres_connection_timeout"]
    assert len(timeout_facts) == 1


