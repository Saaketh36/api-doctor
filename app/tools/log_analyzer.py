import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class LogPattern:
    category: str
    description: str
    pattern: Pattern[str]
    confidence: float


class LogAnalyzer:
    """Extracts deterministic facts from logs without calling an LLM."""

    def __init__(self) -> None:
        self.patterns = [
            LogPattern(
                category="postgres_connection_timeout",
                description="PostgreSQL connection attempt timed out.",
                pattern=re.compile(
                    r"(connection timed out|timeout expired|connect timeout|operation timed out|"
                    r"statement timeout|canceling statement due to statement timeout|"
                    r"timed out waiting for (?:a )?connection|pool (?:timed out|timeout)|"
                    r"queuepool.*connection timed out)",
                    re.IGNORECASE,
                ),
                confidence=0.88,
            ),
            LogPattern(
                category="postgres_connection_refused",
                description="PostgreSQL host refused the connection.",
                pattern=re.compile(
                    r"(connection refused|accepting tcp/ip connections|server closed the connection unexpectedly|"
                    r"connection to server at .* failed: connection refused)",
                    re.IGNORECASE,
                ),
                confidence=0.86,
            ),
            LogPattern(
                category="postgres_authentication_failed",
                description="PostgreSQL rejected the supplied credentials.",
                pattern=re.compile(
                    r"(password authentication failed|authentication failed|no pg_hba\.conf entry|"
                    r"role [\"']?[\w.-]+[\"']? does not exist|user [\"']?[\w.-]+[\"']? does not exist|"
                    r"peer authentication failed)",
                    re.IGNORECASE,
                ),
                confidence=0.90,
            ),
            LogPattern(
                category="postgres_database_missing",
                description="Requested PostgreSQL database does not exist.",
                pattern=re.compile(
                    r'(database ["\']?([\w.-]+)["\']? does not exist|fatal:\s+database ["\']?([\w.-]+)["\']? does not exist|unknown database)',
                    re.IGNORECASE,
                ),
                confidence=0.92,
            ),
            LogPattern(
                category="postgres_host_resolution_failed",
                description="Database hostname could not be resolved.",
                pattern=re.compile(
                    r"(could not translate host name|name or service not known|getaddrinfo failed|"
                    r"nodename nor servname provided|temporary failure in name resolution|no address associated with hostname)",
                    re.IGNORECASE,
                ),
                confidence=0.89,
            ),
            LogPattern(
                category="postgres_too_many_connections",
                description="PostgreSQL connection limit or pool capacity was exhausted.",
                pattern=re.compile(
                    r"(too many connections|remaining connection slots are reserved|connection pool exhausted|"
                    r"sorry, too many clients already|pool size limit .* reached|queuepool limit .* reached)",
                    re.IGNORECASE,
                ),
                confidence=0.90,
            ),
            LogPattern(
                category="postgres_ssl_error",
                description="PostgreSQL SSL negotiation or certificate validation failed.",
                pattern=re.compile(
                    r"(ssl error|certificate verify failed|certificate verification failed|"
                    r"server does not support ssl|ssl syscall error|ssl connection has been closed unexpectedly|"
                    r"routines:.*certificate|routines:.*ssl|invalid sslmode|unrecognized sslmode)",
                    re.IGNORECASE,
                ),
                confidence=0.85,
            ),
        ]

    def analyze(self, error_message: str, logs: str) -> list[dict[str, object]]:
        text = f"{error_message}\n{logs}"
        facts: list[dict[str, object]] = []

        for log_pattern in self.patterns:
            for match in log_pattern.pattern.finditer(text):
                facts.append(
                    {
                        "category": log_pattern.category,
                        "description": log_pattern.description,
                        "matched_text": match.group(0),
                        "confidence": log_pattern.confidence,
                    }
                )

        return self._dedupe(facts)

    def _dedupe(self, facts: list[dict[str, object]]) -> list[dict[str, object]]:
        seen: set[tuple[object, object]] = set()
        unique_facts: list[dict[str, object]] = []

        for fact in facts:
            key = (fact["category"], str(fact["matched_text"]).lower())
            if key in seen:
                continue
            seen.add(key)
            unique_facts.append(fact)

        return unique_facts

