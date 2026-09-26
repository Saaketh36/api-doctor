import tempfile
from pathlib import Path

from app.tools.code_searcher import CodeSearcher


def test_search_returns_empty_when_root_is_none() -> None:
    searcher = CodeSearcher()
    assert searcher.search(None, "POST /users") == []


def test_search_returns_empty_when_root_does_not_exist() -> None:
    searcher = CodeSearcher()
    assert searcher.search("non/existent/path/that/does/not/exist", "POST /users") == []


def test_search_finds_database_and_endpoint_references() -> None:
    searcher = CodeSearcher()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create a sample python file
        py_file = tmp_path / "database.py"
        py_file.write_text(
            "import os\n"
            "DATABASE_URL = os.getenv('DATABASE_URL')\n"
            "engine = create_engine(DATABASE_URL, pool_size=10, connect_timeout=5)\n",
            encoding="utf-8",
        )

        # Create an endpoint file
        routes_file = tmp_path / "routes.py"
        routes_file.write_text(
            "@app.post('/users')\n"
            "def create_user():\n"
            "    db = get_db()\n"
            "    return {'status': 'created'}\n",
            encoding="utf-8",
        )

        results = searcher.search(str(tmp_path), "POST /users")

        assert len(results) >= 2
        paths = [r.path for r in results]
        assert "database.py" in paths
        assert "routes.py" in paths

        # Check line numbers and snippets
        db_ref = next(r for r in results if r.path == "database.py")
        assert "DATABASE_URL" in db_ref.snippet
        assert db_ref.line == 2


def test_search_ignores_excluded_directories() -> None:
    searcher = CodeSearcher()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create file in ignored dir .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.py").write_text("DATABASE_URL = 'postgres://secret'", encoding="utf-8")

        # Create file in ignored dir .venv
        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "db.py").write_text("DATABASE_URL = 'postgres://secret'", encoding="utf-8")

        # Create valid source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "db.py").write_text("DATABASE_URL = 'postgres://app'", encoding="utf-8")

        results = searcher.search(str(tmp_path), "GET /items")
        paths = [r.path.replace("\\", "/") for r in results]

        assert "src/db.py" in paths
        assert not any(".git" in p for p in paths)
        assert not any(".venv" in p for p in paths)


def test_search_sanitizes_potential_secrets_in_snippets() -> None:
    searcher = CodeSearcher()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_file = tmp_path / "settings.py"
        config_file.write_text(
            "DATABASE_URL = 'postgresql://dbuser:supersecretpass@localhost:5432/mydb'\n"
            "POSTGRES_PASSWORD = 'my_top_secret_password'\n",
            encoding="utf-8",
        )

        results = searcher.search(str(tmp_path), "GET /status")
        snippets = [r.snippet for r in results]

        # Verify URI password was redacted
        assert any("postgresql://dbuser:***@localhost:5432/mydb" in s for s in snippets)
        # Verify variable assignment was redacted
        assert any("POSTGRES_PASSWORD = '***'" in s for s in snippets)

