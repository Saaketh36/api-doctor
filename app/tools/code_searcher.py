import re
from pathlib import Path

from app.models.diagnosis import CodeReference


class CodeSearcher:
    """Searches source files for database and endpoint context."""

    DEFAULT_TERMS = (
        "DATABASE_URL",
        "POSTGRES",
        "postgresql",
        "psycopg",
        "asyncpg",
        "create_engine",
        "SessionLocal",
        "pool_size",
        "connect_timeout",
        "pool_timeout",
        "sqlalchemy",
        "tortoise",
        "databases",
        "get_db",
        "db_session",
        "max_connections",
    )
    EXTENSIONS = {".py", ".env", ".toml", ".yaml", ".yml", ".json", ".ini", ".conf", ".sql"}
    IGNORED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "env",
        "apidoc",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".eggs",
        "site-packages",
    }

    def search(self, root: str | None, endpoint: str, terms: tuple[str, ...] | None = None) -> list[CodeReference]:
        if not root:
            return []

        try:
            root_path = Path(root).expanduser().resolve()
        except Exception:
            return []

        if not root_path.exists() or not root_path.is_dir():
            return []

        search_terms = self._build_terms(endpoint, terms)
        references: list[CodeReference] = []

        for path in self._iter_files(root_path):
            references.extend(self._search_file(path, root_path, search_terms))
            if len(references) >= 25:
                break

        return references[:25]

    def _build_terms(self, endpoint: str, terms: tuple[str, ...] | None) -> tuple[str, ...]:
        clean_endpoint = endpoint.replace("/", " ").replace(":", " ").replace("-", " ")
        endpoint_parts = tuple(part for part in clean_endpoint.split() if len(part) > 2)
        return tuple(dict.fromkeys((terms or self.DEFAULT_TERMS) + endpoint_parts))

    def _iter_files(self, root: Path):
        for path in root.rglob("*"):
            if any(
                part in self.IGNORED_DIRS or part.endswith(".egg-info") or part.endswith(".dist-info")
                for part in path.parts
            ):
                continue
            if path.is_file() and path.suffix.lower() in self.EXTENSIONS:
                yield path

    def _search_file(self, path: Path, root: Path, terms: tuple[str, ...]) -> list[CodeReference]:
        references: list[CodeReference] = []

        try:
            # Skip very large files (> 2MB)
            if path.stat().st_size > 2 * 1024 * 1024:
                return references
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return references

        lowered_terms = tuple(term.lower() for term in terms)
        for line_number, line in enumerate(lines, start=1):
            normalized = line.lower()
            if any(term in normalized for term in lowered_terms):
                sanitized_line = self._sanitize_snippet(line.strip())
                references.append(
                    CodeReference(
                        path=str(path.relative_to(root)),
                        line=line_number,
                        snippet=sanitized_line[:240],
                    )
                )

        return references

    SECRET_ASSIGN_PATTERN = re.compile(
        r"([a-zA-Z0-9_]*(?:password|secret|key|token|auth|credential)[a-zA-Z0-9_]*\s*[:=]\s*['\"]?)([^'\",;\s]+)(['\"]?)",
        re.IGNORECASE,
    )
    URI_SECRET_PATTERN = re.compile(
        r"(://[^:]+:)([^@]+)(@)",
        re.IGNORECASE,
    )

    def _sanitize_snippet(self, line: str) -> str:
        # Redact URI passwords e.g. postgresql://user:pass@host/db -> postgresql://user:***@host/db
        sanitized = self.URI_SECRET_PATTERN.sub(r"\1***\3", line)
        # Redact variable assignments e.g. password = 'xxx' -> password = '***'
        sanitized = self.SECRET_ASSIGN_PATTERN.sub(r"\1***\3", sanitized)
        return sanitized



