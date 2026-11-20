"""Runtime settings. Secrets stay in the environment, never in the browser."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    data_dir: Path
    cors_origins: tuple[str, ...]
    search_concurrency: int = 3
    search_limit: int = 8
    candidate_limit: int = 5
    batch_limit: int = 40
    add_chunk_size: int = 25
    max_csv_bytes: int = 2_000_000

    @property
    def auth_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def load_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    _load_env_file(backend_root / ".env")
    _load_env_file(backend_root.parent / ".env")
    data_dir = Path(os.environ.get("TRACKTRANSFER_DATA_DIR", backend_root / "data")).resolve()
    origins = os.environ.get(
        "TRACKTRANSFER_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return Settings(
        client_id=os.environ.get("YTMUSIC_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("YTMUSIC_CLIENT_SECRET", "").strip(),
        data_dir=data_dir,
        cors_origins=tuple(part.strip() for part in origins.split(",") if part.strip()),
    )
