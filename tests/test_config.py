from src.config import (
    Settings,
    configure_logging,
    get_settings,
)


def test_settings_reads_environment_values(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "GEMINI_MODEL",
        "gemini-test-model",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "sqlite:///custom.db",
    )
    monkeypatch.setenv(
        "MAX_UPLOAD_SIZE_MB",
        "12",
    )
    monkeypatch.setenv(
        "OCR_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "OCR_LANGUAGES",
        "en,hi",
    )
    monkeypatch.setenv(
        "LOG_LEVEL",
        "DEBUG",
    )

    settings = Settings.from_environment()

    assert settings.gemini_model == "gemini-test-model"
    assert settings.database_url == "sqlite:///custom.db"
    assert settings.max_upload_size_bytes == 12 * 1024 * 1024
    assert settings.ocr_enabled is False
    assert settings.ocr_language_list == ["en", "hi"]
    assert settings.log_level == "DEBUG"


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second


def test_configure_logging_accepts_invalid_level(
    monkeypatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "LOG_LEVEL",
        "NOT_A_LEVEL",
    )

    assert configure_logging() is None
