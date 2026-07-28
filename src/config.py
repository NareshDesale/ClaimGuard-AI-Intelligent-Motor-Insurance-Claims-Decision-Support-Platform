import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "claimguard.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}

    with path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key:
                values[key] = value

    return values


def get_env_value(
    key: str,
    default: str | None = None,
) -> str | None:
    return os.getenv(
        key,
        load_env_file().get(key, default),
    )


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    return default


def parse_int(
    value: str | None,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return min(
        max(parsed, minimum),
        maximum,
    )


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    database_url: str = DEFAULT_DATABASE_URL
    max_upload_size_mb: int = 10
    ocr_enabled: bool = True
    ocr_languages: str = "en"
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            gemini_api_key=get_env_value("GEMINI_API_KEY"),
            gemini_model=(
                get_env_value("GEMINI_MODEL", "gemini-3.6-flash")
                or "gemini-3.6-flash"
            ),
            database_url=(
                get_env_value("DATABASE_URL", DEFAULT_DATABASE_URL)
                or DEFAULT_DATABASE_URL
            ),
            max_upload_size_mb=parse_int(
                get_env_value("MAX_UPLOAD_SIZE_MB"),
                default=10,
                minimum=1,
                maximum=100,
            ),
            ocr_enabled=parse_bool(
                get_env_value("OCR_ENABLED"),
                default=True,
            ),
            ocr_languages=(
                get_env_value("OCR_LANGUAGES", "en")
                or "en"
            ),
            log_level=(
                get_env_value("LOG_LEVEL", "INFO")
                or "INFO"
            ),
        )

    @property
    def ocr_language_list(self) -> list[str]:
        languages = [
            language.strip()
            for language in self.ocr_languages.split(",")
            if language.strip()
        ]

        return languages or ["en"]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()


def configure_logging() -> None:
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(
        logging,
        level_name,
        logging.INFO,
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )
