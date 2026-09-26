# API Doctor — The Complete Project & Architecture Guide

> A comprehensive, beginner-friendly guide covering every minute detail of the **API Doctor** codebase, architecture, lifecycle, and interview talking points.

---

## Table of Contents
1. [The Big Picture: Problem & Solution](#1-the-big-picture-problem--solution)
2. [The 4-Step Mental Model & Architecture](#2-the-4-step-mental-model--architecture)
3. [File-by-File Breakdown](#3-file-by-file-breakdown)
   - [app/main.py](#31-appmainpy--the-web-server-entrypoint)
   - [app/core/config.py](#32-appcoreconfigpy--environment--settings)
   - [app/models/diagnosis.py](#33-appmodelsdiagnosispy--pydantic-contracts)
   - [app/tools/log_analyzer.py](#34-apptoolslog_analyzerpy--regex-engine)
   - [app/tools/code_searcher.py](#35-apptoolscode_searcherpy--safe-code-scanner)
   - [app/services/llm_client.py](#36-appservicesllm_clientpy--groq-ai-client)
   - [app/services/api_doctor.py](#37-appservicesapi_doctorpy--the-orchestrator)
4. [Tracing a Request Lifecycle End-to-End](#4-tracing-a-request-lifecycle-end-to-end)
5. [The Test Suite & Quality Assurance](#5-the-test-suite--quality-assurance)
6. [Engineering Concepts & Best Practices](#6-engineering-concepts--best-practices)
7. [How to Explain This Project in an Interview](#7-how-to-explain-this-project-in-an-interview)

---

## 1. The Big Picture: Problem & Solution

### The Real-World Scenario
When a backend server throws a `500 Internal Server Error`, on-call engineers are faced with hundreds of lines of stack traces. Finding the root cause is stressful, time-consuming, and error-prone.

### Why Not Just Use ChatGPT/Raw LLM?
1. **Security Vulnerability:** Developers accidentally paste secrets, database passwords, or customer PII into public AI prompts.
2. **Hallucinations:** Pure LLMs can invent non-existent flags or diagnose incorrectly without grounding.
3. **High Latency & Costs:** Pushing 10,000-line logs to cloud models is slow and expensive.
4. **Lack of Codebase Context:** A public LLM does not know how your local application configures its database connections.

### How API Doctor Solves It
API Doctor uses a **deterministic-first pipeline**:
- Extracts verified failure facts using **sub-millisecond regular expressions**.
- Inspects local codebase context while **automatically redacting secrets**.
- Passes only high-signal facts to **Groq LLM** (`openai/gpt-oss-120b`) for rapid semantic synthesis.
- Delivers a structured JSON diagnosis in less than **1 second**.

---

## 2. The 4-Step Mental Model & Architecture

```
                    +--------------------------------+
                    |       Client / Developer       |
                    |  Sends failing route & logs    |
                    +---------------+----------------+
                                    |
                                    v
                     +--------------+--------------+
                     |        app/main.py          |
                     |  FastAPI receives the HTTP  |
                     |   POST request at /diagnose |
                     +--------------+--------------+
                                    |
                                    v
                     +--------------+--------------+
                     |  app/models/diagnosis.py    |
                     |  Pydantic validates input:  |
                     |  non-empty, strips spaces   |
                     +--------------+--------------+
                                    |
                     +--------------+--------------+
                     |
                     |--> 1. LogAnalyzer (Regex Engine)
                     |       Extracts deterministic facts:
                     |       "PostgreSQL connection timed out (88% confidence)"
                     |
                     |--> 2. CodeSearcher (File Scanner)
                     |       Finds DB files (database.py)
                     |       Masks credentials: postgresql://user:***@host/db
                     |
                     v
      +-----------------------------------------------------------+
      |               app/services/api_doctor.py                  |
      |                 The Orchestrator / Doctor                 |
      |                                                           |
      | Takes extracted facts + safe code references and builds   |
      | a targeted prompt for the Groq LLM.                       |
      +-----------------------------+-----------------------------+
                                    |
                                    v
                     +--------------+--------------+
                     |  app/services/llm_client.py |
                     |  Calls Groq's high-speed    |
                     |  inference engine (Async)   |
                     +--------------+--------------+
                                    |
                                    v
                     +--------------+--------------+
                     |     Final JSON Response     |
                     |  - Root Cause               |
                     |  - Confidence Score         |
                     |  - Verified Evidence List   |
                     |  - Step-by-Step Fixes       |
                     +-----------------------------+
```

---

## 3. File-by-File Breakdown

### 3.1 `app/main.py` — The Web Server Entrypoint
- **`app = FastAPI(...)`**: Creates the FastAPI instance with OpenAPI docs at `/docs`.
- **`get_doctor() -> APIDoctor`**: Dependency provider for FastAPI's dependency injection (`Depends(get_doctor)`).
- **`GET /health`**: Health check for container orchestrators and load balancers.
- **`POST /diagnose`**: Main asynchronous route accepting `DiagnosisRequest` and returning `DiagnosisResponse`.

### 3.2 `app/core/config.py` — Environment & Settings
- Powered by `pydantic-settings` via `BaseSettings`.
- Loads configuration from `.env` with fallback defaults (`groq_model="openai/gpt-oss-120b"`, `groq_timeout_seconds=10.0`).
- **`clean_api_key()`**: A field validator that strips leading/trailing spaces from API keys.

### 3.3 `app/models/diagnosis.py` — Pydantic Contracts
- **`DiagnosisRequest`**: Enforces non-empty strings on `endpoint`, `error_message`, and `logs`. Rejects empty or whitespace-only inputs with HTTP 422.
- **`EvidenceItem`**: Tracks the source (`log_analyzer`, `code_searcher`, `groq_llm`), detail text, and confidence level.
- **`CodeReference`**: Represents a file match (`path`, `line`, `snippet`).
- **`ToolResults`**: Holds raw extracted facts and code references.
- **`DiagnosisResponse`**: Strongly-typed response schema with `root_cause`, `confidence`, `category`, `evidence`, `fixes`, and `debugging_steps`.

### 3.4 `app/tools/log_analyzer.py` — Regex Engine
Deterministic regex matcher covering 7 PostgreSQL failure families:
1. `postgres_connection_timeout` (confidence: 0.88)
2. `postgres_connection_refused` (confidence: 0.86)
3. `postgres_authentication_failed` (confidence: 0.90)
4. `postgres_database_missing` (confidence: 0.92)
5. `postgres_host_resolution_failed` (confidence: 0.89)
6. `postgres_too_many_connections` (confidence: 0.90)
7. `postgres_ssl_error` (confidence: 0.85)
- **`_dedupe()`**: Merges duplicate matches in multi-line logs.

### 3.5 `app/tools/code_searcher.py` — Safe Code Scanner
- Searches source files for database and endpoint keywords (`DATABASE_URL`, `create_engine`, `psycopg`, etc.).
- **`IGNORED_DIRS`**: Skips `.git`, `.venv`, `apidoc`, `node_modules`, `dist`, and build caches.
- **`_sanitize_snippet()`**: Masks credentials using regex:
  - Redacts URI passwords: `postgresql://user:pass@host` -> `postgresql://user:***@host`
  - Redacts variable assignments: `password = "secret"` -> `password = '***'`
- Limits search to max 25 references and skips files larger than 2MB.

### 3.6 `app/services/llm_client.py` — Groq AI Client
- Asynchronous HTTP client using `httpx.AsyncClient`.
- Sends system and user prompts to Groq's chat completions endpoint.
- Graceful error handling: handles timeouts (`httpx.TimeoutException`), HTTP errors, and network failures by falling back to deterministic facts without failing the request.

### 3.7 `app/services/api_doctor.py` — The Orchestrator
- Coordinates `LogAnalyzer`, `CodeSearcher`, and `GroqLLMClient`.
- Identifies the primary fact with the highest confidence score.
- Maps the primary failure category to domain-specific remediation fixes and practical terminal debugging steps.

---

## 4. Tracing a Request Lifecycle End-to-End

```
1. Client POSTs JSON to /diagnose:
   {
     "endpoint": "POST /users",
     "error_message": "500 database connection timeout",
     "logs": "psycopg2.OperationalError: could not connect to server: Connection timed out"
   }

2. FastAPI validates payload via DiagnosisRequest (models/diagnosis.py).
3. LogAnalyzer matches regex pattern "connection timed out" (confidence: 0.88).
4. CodeSearcher scans local project directory (if code_root provided) and redacts secrets.
5. APIDoctor builds a focused prompt with extracted facts and calls GroqLLMClient.
6. Groq generates concise root cause reasoning in ~200-300ms.
7. APIDoctor populates category-specific fixes and debugging commands.
8. Client receives structured JSON response in ~0.8s.
```

---

## 5. The Test Suite & Quality Assurance

API Doctor has **29 automated tests** in the `tests/` directory with a 100% pass rate:

```bash
pytest -v
```

- **`test_api.py` (5 tests):** Validates HTTP routes, 422 input validation, and mocks the doctor dependency so tests run offline without network latency.
- **`test_api_doctor.py` (4 tests):** Tests the end-to-end orchestration logic with mock LLM and code searchers across all 7 PostgreSQL categories.
- **`test_code_searcher.py` (5 tests):** Creates temporary file trees to verify that database keywords are found, ignored directories are skipped, and secrets are properly redacted with `***`.
- **`test_llm_client.py` (6 tests):** Simulates 401 unauthorized errors, network timeouts, unconfigured keys, and malformed JSON using monkeypatching.
- **`test_log_analyzer.py` (9 tests):** Validates regex accuracy across all failure categories and checks match deduplication.

---

## 6. Engineering Concepts & Best Practices

| Concept | How It Is Used in API Doctor |
| :--- | :--- |
| **Deterministic-First** | Uses regex for zero-latency, 100% predictable fact extraction; uses LLM solely for explanation and synthesis. |
| **AsyncIO & Concurrency** | Uses `async def` routes and non-blocking `httpx.AsyncClient` for high I/O throughput. |
| **Defense-in-Depth** | Code snippets redact secrets via regex before sending them to the LLM or client. |
| **Dependency Injection** | `Depends(get_doctor)` decouples route logic from service instantiation, enabling simple mock replacement during tests. |
| **CI/CD** | GitHub Actions (`.github/workflows/ci.yml`) runs the full test suite automatically on every push and pull request. |

---

## 7. How to Explain This Project in an Interview

### 30-Second Elevator Pitch
> *"I built **API Doctor**, an asynchronous backend failure diagnosis service using FastAPI and Pydantic v2. Instead of manually sifting through hundreds of lines of stack traces, API Doctor uses a deterministic-first pipeline: it extracts verified failure facts using sub-millisecond regex analyzers, retrieves relevant code context while masking secrets, and uses the Groq LLM API to deliver structured root causes, confidence scores, and step-by-step remediation plans in under one second."*

### Key Interview Talking Points
1. **Why not a pure LLM?**
   *"Blindly passing raw logs to an LLM creates token bloat, high latency, security risks, and hallucinations. API Doctor grounds the diagnosis in deterministic facts first."*
2. **How is security handled?**
   *"The codebase scanner automatically sanitizes connection URIs and variable assignments, replacing passwords and auth tokens with asterisks before passing them to the model."*
3. **How does it handle scale and resilience?**
   *"The service is asynchronous and features graceful fallback: if Groq times out or fails, the engine falls back to deterministic rule-based output without throwing a 500 error."*
