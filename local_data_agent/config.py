from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ConnectionType = Literal["database", "folder"]


@dataclass(slots=True)
class LocalConnection:
    """Connection metadata persisted only on the local machine."""

    type: ConnectionType
    name: str
    database_uri: str | None = None
    folder_path: str | None = None

    def public_dict(self) -> dict[str, str | None]:
        """Return a sanitized representation safe for browser/LLM prompts."""
        return {
            "type": self.type,
            "name": self.name,
            "database_uri": mask_database_uri(self.database_uri) if self.database_uri else None,
            "folder_path": Path(self.folder_path).name if self.folder_path else None,
        }


class ConfigStore:
    """Small JSON-backed store for local-only connection settings."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(os.environ.get("LOCAL_DATA_AGENT_HOME", Path.home() / ".local_data_agent"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_file = self.root / "config.json"
        self.exports_dir = self.root / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def save_connection(self, connection: LocalConnection) -> None:
        self.config_file.write_text(json.dumps(asdict(connection), indent=2), encoding="utf-8")
        try:
            self.config_file.chmod(0o600)
        except OSError:
            pass

    def load_connection(self) -> LocalConnection | None:
        if not self.config_file.exists():
            return None
        data = json.loads(self.config_file.read_text(encoding="utf-8"))
        if data.get("type") not in {"database", "folder"}:
            return None
        return LocalConnection(**data)

    def clear(self) -> None:
        if self.config_file.exists():
            self.config_file.unlink()


def mask_database_uri(uri: str | None) -> str | None:
    """Mask credentials in a database URI before displaying or prompting."""
    if not uri:
        return None
    if "@" not in uri or "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"
