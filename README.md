# API Doctor

[![CI](https://github.com/Saaketh36/api-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/Saaketh36/api-doctor/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**API Doctor** is a production failure diagnosis engine for backend APIs. When endpoints fail, it takes the failing route, error messages, and raw logs, analyzes them with **deterministic regex extractors**, retrieves contextual code references with automated credential masking, and synthesizes root causes with actionable fixes using the **Groq LLM API**.

---

## Architecture Overview

Rather than blindly piping raw logs to an LLM (which introduces token bloat, latency, and hallucinations), API Doctor follows a **deterministic-first** pipeline:

```
                      +-------------------+
                      |   Client Request  |
                      |  (Route, Logs)    |
                      +---------+---------+
                                |
                                v
               +----------------+----------------+
               |                                 |
               v                                 v
      +-----------------+              +--------------------+
      |   LogAnalyzer   |              |    CodeSearcher    |
      |  (Regex Engine) |              |  (Snippet Search)  |
      +--------+--------+              +---------+----------+
               |                                 |
         Extracted Facts               Masked Source Refs
         (Confidence > 0.85)           (Secrets Redacted)
               |                                 |
               +----------------+----------------+
                                |
                                v
                      +-------------------+
                      |    APIDoctor      |
                      |  (Orchestrator)   |
                      +---------+---------+
                                |
                                v
                      +-------------------+
                      |   GroqLLMClient   |
                      |  (LLM Synthesis)  |
                      +---------+---------+
                                |
                                v
                      +-------------------+
                      | Structured Output |
                      |  (JSON Diagnosis) |
                      +-------------------+
```

### Core Components

* **`LogAnalyzer` (`app/tools/log_analyzer.py`)**: Deterministic pattern matcher that extracts failure facts (timeouts, connection refusals, pool exhaustion, missing databases, auth errors) with associated confidence scores.
* **`CodeSearcher` (`app/tools/code_searcher.py`)**: File-system scanner that locates relevant database configuration and route handlers while automatically redacting passwords, auth tokens, and connection strings (`***`).
* **`GroqLLMClient` (`app/services/llm_client.py`)**: Asynchronous HTTP client communicating with Groq (`openai/gpt-oss-120b`) for rapid semantic synthesis and step-by-step troubleshooting recommendations.
* **`APIDoctor` (`app/services/api_doctor.py`)**: Coordinates tool facts and LLM reasoning into a strongly-typed Pydantic response schema.

---

## Quick Start

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Saaketh36/api-doctor.git
cd api-doctor

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:

```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
APP_ENV=local
```

### 4. Run the Service

```bash
uvicorn app.main:app --reload --port 8000
```

Open interactive Swagger documentation at **`http://localhost:8000/docs`**.

---

## Example Usage

### Diagnose a Database Connection Failure

```bash
curl -X POST http://localhost:8000/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "POST /users",
    "error_message": "500 database connection timeout",
    "logs": "psycopg2.OperationalError: could not connect to server: Connection timed out"
  }'
```

### Example Response

```json
{
  "root_cause": "PostgreSQL connection attempt timed out.",
  "confidence": 0.88,
  "category": "postgres_connection_timeout",
  "evidence": [
    {
      "source": "log_analyzer",
      "detail": "PostgreSQL connection attempt timed out.",
      "confidence": 0.88
    },
    {
      "source": "groq_llm",
      "detail": "The database host is unreachable. Verify network routing, firewall rules, and container network definitions.",
      "confidence": 0.85
    }
  ],
  "fixes": [
    "Verify the database host and port are reachable from the API runtime.",
    "Check firewall, VPC, Docker network, or security group rules.",
    "Set a reasonable connection timeout and inspect slow DNS or overloaded database startup."
  ],
  "debugging_steps": [
    "Reproduce the failing request once and capture the full timestamped log block.",
    "Print the active database connection settings without exposing secrets.",
    "Test connectivity from the same runtime environment as the API.",
    "Run a TCP connectivity check (e.g. nc -zv or telnet) to the database host and port.",
    "Compare timeout timing with load balancer, firewall, and database server metrics."
  ],
  "tool_results": {
    "log_facts": [
      {
        "category": "postgres_connection_timeout",
        "description": "PostgreSQL connection attempt timed out.",
        "matched_text": "Connection timed out",
        "confidence": 0.88
      }
    ],
    "code_references": []
  }
}
```

---

## Running Tests

The test suite covers unit logic, mocking, integration endpoints, and error handling. Tests execute cleanly without external network calls:

```bash
pytest -v
```

Output:
```text
tests/test_api.py .....                                    [ 17%]
tests/test_api_doctor.py ....                              [ 31%]
tests/test_code_searcher.py .....                          [ 48%]
tests/test_llm_client.py ......                            [ 68%]
tests/test_log_analyzer.py .........                       [100%]
====================== 29 passed in 0.83s =======================
```

---

## License

This project is licensed under the [MIT License](LICENSE).
