from app.models.diagnosis import CodeReference, DiagnosisRequest, DiagnosisResponse, EvidenceItem, ToolResults
from app.services.llm_client import GroqLLMClient
from app.tools.code_searcher import CodeSearcher
from app.tools.log_analyzer import LogAnalyzer


class APIDoctor:
    def __init__(
        self,
        log_analyzer: LogAnalyzer | None = None,
        code_searcher: CodeSearcher | None = None,
        llm_client: GroqLLMClient | None = None,
    ) -> None:
        self.log_analyzer = log_analyzer or LogAnalyzer()
        self.code_searcher = code_searcher or CodeSearcher()
        self.llm_client = llm_client or GroqLLMClient()

    async def diagnose(self, request: DiagnosisRequest) -> DiagnosisResponse:
        log_facts = self.log_analyzer.analyze(request.error_message, request.logs)
        code_references = self.code_searcher.search(request.code_root, request.endpoint)

        llm_reasoning = await self._get_llm_reasoning(request, log_facts, code_references)
        return self._build_response(log_facts, code_references, llm_reasoning)

    async def _get_llm_reasoning(
        self,
        request: DiagnosisRequest,
        log_facts: list[dict[str, object]],
        code_references: list[CodeReference],
    ) -> str | None:
        prompt_lines = [
            "Diagnose this API error using the supplied deterministic facts and source context.\n",
            f"Endpoint: {request.endpoint}",
            f"Error message: {request.error_message}",
            f"Log facts: {log_facts}",
        ]
        if code_references:
            refs_summary = "\n".join(f"- {ref.path}:{ref.line}: {ref.snippet}" for ref in code_references[:5])
            prompt_lines.append(f"Relevant code references:\n{refs_summary}")
        prompt_lines.append(f"Raw logs:\n{request.logs[:3000]}")
        prompt = "\n\n".join(prompt_lines)

        return await self.llm_client.reason(prompt)

    def _build_response(
        self,
        log_facts: list[dict[str, object]],
        code_references: list[CodeReference],
        llm_reasoning: str | None,
    ) -> DiagnosisResponse:
        primary_fact = max(log_facts, key=lambda fact: float(fact["confidence"]), default=None)

        if primary_fact is None:
            category = "unknown"
            root_cause = "No known PostgreSQL error pattern was detected."
            confidence = 0.25
            fixes = [
                "Capture the complete stack trace and database driver error.",
                "Check API logs around the first failing request.",
                "Confirm the database service, host, port, credentials, and network path.",
            ]
        else:
            category = str(primary_fact["category"])
            root_cause = str(primary_fact["description"])
            confidence = float(primary_fact["confidence"])
            fixes = self._fixes_for(category)

        evidence = [
            EvidenceItem(
                source="log_analyzer",
                detail=str(fact["description"]),
                confidence=float(fact["confidence"]),
            )
            for fact in log_facts
        ]

        if code_references:
            evidence.append(
                EvidenceItem(
                    source="code_searcher",
                    detail=f"Identified {len(code_references)} related code reference(s) in project files.",
                    confidence=0.75,
                )
            )

        if llm_reasoning:
            evidence.append(
                EvidenceItem(
                    source="groq_llm",
                    detail=llm_reasoning[:800],
                    confidence=0.85,
                )
            )

        return DiagnosisResponse(
            root_cause=root_cause,
            confidence=confidence,
            category=category,
            evidence=evidence,
            fixes=fixes,
            debugging_steps=self._debugging_steps_for(category),
            tool_results=ToolResults(log_facts=log_facts, code_references=code_references),
        )

    def _fixes_for(self, category: str) -> list[str]:
        fixes_by_category = {
            "postgres_connection_timeout": [
                "Verify the database host and port are reachable from the API runtime.",
                "Check firewall, VPC, Docker network, or security group rules.",
                "Set a reasonable connection timeout and inspect slow DNS or overloaded database startup.",
            ],
            "postgres_connection_refused": [
                "Confirm PostgreSQL is running and listening on the configured host and port.",
                "Check container service names and exposed ports.",
                "Verify the API is not pointing at localhost from inside a container.",
            ],
            "postgres_authentication_failed": [
                "Verify username and password in the API environment.",
                "Rotate credentials if secrets are stale.",
                "Check PostgreSQL user permissions and pg_hba.conf for the target database.",
            ],
            "postgres_database_missing": [
                "Create the configured database or update DATABASE_URL to the existing database name.",
                "Run migrations against the correct environment.",
            ],
            "postgres_host_resolution_failed": [
                "Fix the database hostname in configuration.",
                "Check DNS, Docker Compose service names, and Kubernetes service names.",
            ],
            "postgres_too_many_connections": [
                "Reduce API connection pool size or increase PostgreSQL max_connections.",
                "Ensure sessions/connections are closed after each request.",
                "Add pooling through PgBouncer for high concurrency workloads.",
            ],
            "postgres_ssl_error": [
                "Align sslmode with the database provider requirements.",
                "Install or configure the correct CA certificate.",
            ],
        }
        return fixes_by_category.get(category, ["Collect more logs and inspect database connectivity configuration."])

    def _debugging_steps_for(self, category: str) -> list[str]:
        common_steps = [
            "Reproduce the failing request once and capture the full timestamped log block.",
            "Print the active database connection settings without exposing secrets.",
            "Test connectivity from the same runtime environment as the API.",
        ]
        category_steps = {
            "postgres_connection_timeout": [
                "Run a TCP connectivity check (e.g. nc -zv or telnet) to the database host and port.",
                "Compare timeout timing with load balancer, firewall, and database server metrics.",
            ],
            "postgres_connection_refused": [
                "Check whether PostgreSQL is active (`systemctl status postgresql` or `docker ps`).",
                "Inspect postgresql.conf `listen_addresses` to ensure it is listening on all intended interfaces.",
            ],
            "postgres_authentication_failed": [
                "Verify credentials by connecting directly with `psql -U <user> -h <host> -d <dbname>`.",
                "Inspect pg_hba.conf on the PostgreSQL server for matching auth method (scram-sha-256/md5).",
                "Verify environment variables in the API container/process for typos.",
            ],
            "postgres_database_missing": [
                "List available databases on the PostgreSQL server using `psql -l`.",
                "Confirm whether database migration/creation scripts have run in this environment.",
                "Check DATABASE_URL for typographical errors in the database path.",
            ],
            "postgres_host_resolution_failed": [
                "Run DNS lookup (`nslookup <host>` or `dig <host>`) from the API container.",
                "Check /etc/hosts, Docker Compose network definitions, or Kubernetes CoreDNS.",
                "Ensure there are no accidental spaces or URL protocol prefixes in the DB host setting.",
            ],
            "postgres_too_many_connections": [
                "Query `SELECT count(*) FROM pg_stat_activity;` to inspect active vs idle connections.",
                "Check API code for database session leaks (missing context managers or unclosed sessions).",
                "Verify pool_size and max_overflow settings against PostgreSQL max_connections.",
            ],
            "postgres_ssl_error": [
                "Verify the `sslmode` parameter in DATABASE_URL (disable, require, verify-ca, verify-full).",
                "Check CA certificate file paths, permissions, and validity periods.",
                "Confirm if the PostgreSQL server has SSL enabled in `postgresql.conf` (`ssl = on`).",
            ],
            "unknown": [
                "Add the database driver's original exception class and message to logs.",
                "Search code for the endpoint and database session creation path.",
            ],
        }
        return common_steps + category_steps.get(category, [])


