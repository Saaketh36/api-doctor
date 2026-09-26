# Everything About API Doctor

## Product Definition

API Doctor is an agentic debugging service for API failures. It takes an API endpoint, an error message, and logs, analyzes the evidence with deterministic tools, optionally searches source code for relevant context, then uses LLM reasoning to return a structured diagnosis.

The core output is practical, not chatty:

- root cause
- confidence
- evidence
- likely fixes
- step-by-step debugging plan
- relevant code references when available

## Phase 1 Scope

Phase 1 focuses on PostgreSQL connection and timeout errors. This gives the project a concrete, realistic slice of production debugging without becoming too broad too early.

Included error families:

- database connection refused
- connection timeout
- authentication failure
- database does not exist
- host resolution failure
- too many connections / pool exhaustion
- SSL misconfiguration

Deferred to later phases:

- request validation errors
- authentication and authorization failures
- upstream API failures
- rate limits
- memory, CPU, and resource exhaustion
- automated API testing
- deeper code analysis

## Architecture

```text
app/
  main.py                    FastAPI entrypoint and routes
  core/
    config.py                Environment-backed settings
  models/
    diagnosis.py             Pydantic request/response schemas
  services/
    api_doctor.py            Orchestrates tools and LLM reasoning
    llm_client.py            Groq client wrapper
  tools/
    log_analyzer.py          Regex-only fact extraction
    code_searcher.py         File-system code search
tests/
  test_log_analyzer.py
  test_api_doctor.py
```

The tool boundaries are intentional:

- `LogAnalyzer` extracts facts from logs with regex only.
- `CodeSearcher` searches local files and returns references only.
- `APIDoctor` orchestrates facts, code context, and LLM reasoning.
- `GroqLLMClient` owns external model calls.

## Why This Design Works

The project demonstrates systems thinking rather than a thin chatbot wrapper. Regex extraction makes the first pass reliable and testable. LLM reasoning is reserved for synthesis: deciding what the evidence means and explaining what to do next. The independent tool interfaces make it easy to add new diagnostic capabilities without rewriting the agent.

## Week 1 Roadmap

1. Core scaffolding: done.
2. Log Analyzer: implement regex patterns for PostgreSQL failures.
3. Code Searcher: scan common source files for database and endpoint context.
4. Groq LLM integration: add structured prompt and JSON parsing.
5. End-to-end test: diagnose a sample PostgreSQL timeout from request to response.
6. Documentation: explain setup, examples, and extension patterns.

## API Contract

### `POST /diagnose`

Request:

```json
{
  "endpoint": "POST /users",
  "error_message": "500 database connection timeout",
  "logs": "psycopg2.OperationalError: could not connect to server: Connection timed out",
  "code_root": "optional/path/to/source"
}
```

Response:

```json
{
  "root_cause": "PostgreSQL connection timeout",
  "confidence": 0.86,
  "category": "postgres_connection_timeout",
  "evidence": [],
  "fixes": [],
  "debugging_steps": [],
  "tool_results": {}
}
```

## Extension Pattern

Add a new error type by:

1. Adding regex facts to `LogAnalyzer`.
2. Adding or reusing code-search terms in `CodeSearcher`.
3. Extending the APIDoctor fallback reasoning.
4. Adding focused tests.
5. Optionally improving the LLM prompt once Groq is configured.

## Portfolio Story

API Doctor is strong portfolio material because it is useful, scoped, and extensible. It shows backend structure, deterministic tools, agent orchestration, testing, and practical debugging knowledge.

