"""Media storage adapter. Local disk in development, Cloudflare R2 later."""

from pathlib import Path
from typing import Protocol

from app.config import Settings


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def url(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self, root: Path, base_url: str = "/media") -> None:
        self.root = root.resolve()
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("storage key escapes the storage root")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"


def get_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_dir)
    raise NotImplementedError("R2 storage is wired up in M6")
