import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

ENV_PREFIXES = ("LLM_", "EMBEDDING_", "TTS_", "IMAGE_", "OCR_", "STORAGE_", "R2_", "SUPABASE_")


@pytest.fixture
def settings(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings with no keys and no .env file: proves the app boots key-free."""
    for key in list(os.environ):
        if key.startswith(ENV_PREFIXES) or key.endswith("_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        local_storage_dir=tmp_path,  # type: ignore[arg-type]
        app_env="test",
        checkpointer_backend="memory",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
