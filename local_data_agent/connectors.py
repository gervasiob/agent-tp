from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import LocalConnection

TEXT_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt", ".md", ".log", ".xml", ".yaml", ".yml"}


@dataclass(slots=True)
class DataContext:
    """Sanitized context that can be sent to the LLM."""

    kind: str
    summary: str
    details: dict[str, Any]


class DatabaseConnector:
    """Database connector using SQLAlchemy when available, with native SQLite fallback."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.sqlite_path = sqlite_path_from_uri(uri)
        self.engine: Any | None = None
        if self.sqlite_path is None:
            try:
                from sqlalchemy import create_engine
            except ImportError as exc:  # pragma: no cover - exercised only without optional deps
                raise RuntimeError("Instalá SQLAlchemy para conectarte a bases de datos no SQLite.") from exc
            self.engine = create_engine(uri)

    def describe(self) -> DataContext:
        if self.sqlite_path is not None:
            return self._describe_sqlite()
        return self._describe_sqlalchemy()

    def _describe_sqlalchemy(self) -> DataContext:
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        tables: list[dict[str, Any]] = []
        with self.engine.connect() as connection:
            for table_name in inspector.get_table_names():
                columns = [
                    {"name": column["name"], "type": str(column["type"]), "nullable": column.get("nullable", True)}
                    for column in inspector.get_columns(table_name)
                ]
                try:
                    count = connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
                except Exception:
                    count = None
                tables.append({"name": table_name, "columns": columns, "row_count": count})
        summary = "Base de datos con " + ", ".join(f"{t['name']} ({len(t['columns'])} columnas)" for t in tables)
        return DataContext(kind="database", summary=summary, details={"tables": tables})

    def _describe_sqlite(self) -> DataContext:
        tables: list[dict[str, Any]] = []
        with sqlite3.connect(self.sqlite_path) as conn:
            table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for (table_name,) in table_rows:
                pragma_rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                columns = [{"name": row[1], "type": row[2], "nullable": not bool(row[3])} for row in pragma_rows]
                count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                tables.append({"name": table_name, "columns": columns, "row_count": count})
        summary = "Base de datos con " + ", ".join(f"{t['name']} ({len(t['columns'])} columnas)" for t in tables)
        return DataContext(kind="database", summary=summary, details={"tables": tables})

    def run_readonly_query(self, sql: str, limit: int = 200) -> list[dict[str, Any]]:
        normalized = sql.strip().lower()
        if not normalized.startswith("select"):
            raise ValueError("Solo se permiten consultas SELECT de solo lectura.")
        if self.sqlite_path is not None:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql)
                return [dict(row) for row in cursor.fetchmany(limit)]
        from sqlalchemy import text

        with self.engine.connect() as connection:
            result = connection.execute(text(sql)).mappings().fetchmany(limit)
        return [dict(row) for row in result]


class FolderConnector:
    def __init__(self, folder_path: str) -> None:
        self.folder = Path(folder_path).expanduser().resolve()
        if not self.folder.exists() or not self.folder.is_dir():
            raise ValueError("La carpeta configurada no existe o no es una carpeta.")

    def describe(self) -> DataContext:
        files: list[dict[str, Any]] = []
        total_size = 0
        for file in sorted(self.folder.rglob("*")):
            if not file.is_file():
                continue
            stat = file.stat()
            total_size += stat.st_size
            entry: dict[str, Any] = {
                "name": file.name,
                "relative_path": str(file.relative_to(self.folder)),
                "extension": file.suffix.lower(),
                "size_bytes": stat.st_size,
            }
            if file.suffix.lower() == ".csv":
                entry["columns"] = read_csv_columns(file)
            elif file.suffix.lower() in {".json", ".jsonl"}:
                entry["sample_keys"] = read_json_keys(file)
            files.append(entry)
        summary = f"Carpeta con {len(files)} archivos y {total_size} bytes."
        return DataContext(kind="folder", summary=summary, details={"files": files[:500], "total_size_bytes": total_size})

    def sample_text(self, max_files: int = 5, max_chars_per_file: int = 1500) -> list[dict[str, str]]:
        samples: list[dict[str, str]] = []
        for file in sorted(self.folder.rglob("*")):
            if len(samples) >= max_files:
                break
            if file.is_file() and file.suffix.lower() in TEXT_EXTENSIONS:
                try:
                    content = file.read_text(encoding="utf-8", errors="replace")[:max_chars_per_file]
                except OSError:
                    continue
                samples.append({"relative_path": str(file.relative_to(self.folder)), "content": content})
        return samples


def get_connector(connection: LocalConnection) -> DatabaseConnector | FolderConnector:
    if connection.type == "database" and connection.database_uri:
        return DatabaseConnector(connection.database_uri)
    if connection.type == "folder" and connection.folder_path:
        return FolderConnector(connection.folder_path)
    raise ValueError("La conexión local está incompleta.")


def sqlite_path_from_uri(uri: str) -> str | None:
    parsed = urlparse(uri)
    if parsed.scheme != "sqlite":
        return None
    if parsed.path in {"", "/:memory:"}:
        return ":memory:"
    return unquote(parsed.path)


def read_csv_columns(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def read_json_keys(path: Path) -> list[str]:
    try:
        if path.suffix.lower() == ".jsonl":
            first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
            data = json.loads(first_line)
        else:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(data[0].keys())
    if isinstance(data, dict):
        return list(data.keys())
    return []


def create_sqlite_demo(path: Path) -> None:
    """Create a tiny invoice database useful for demos and tests."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, customer TEXT, subtotal REAL, iva REAL, total REAL)")
        conn.execute("DELETE FROM invoices")
        conn.executemany(
            "INSERT INTO invoices (customer, subtotal, iva, total) VALUES (?, ?, ?, ?)",
            [("ACME", 1000, 210, 1210), ("Globex", 2500, 525, 3025), ("Initech", 800, 168, 968)],
        )
