import pytest
from pydantic import ValidationError

from app.config import Settings


def test_boots_with_no_keys(settings: Settings) -> None:
    assert set(settings.adapter_modes().values()) <= {"mock", "placeholder", "local"}


def test_real_provider_without_key_fails_naming_variable() -> None:
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, llm_provider_main="anthropic", anthropic_api_key="")  # type: ignore[call-arg]


def test_error_never_echoes_values() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, tts_mode="v3", google_api_key="secret-value")  # type: ignore[call-arg]
    assert "secret-value" not in str(exc.value)
