from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "claimguard.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"


def resolve_project_path(value: str | Path) -> Path:
    """Resolve relative settings paths from the repository root."""

    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


class Settings(BaseSettings):
    app_name: str = "ClaimGuard AI"
    app_env: str = "local"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    database_url: str = DEFAULT_DATABASE_URL

    max_upload_size_mb: int = Field(default=10, ge=1, le=100)
    ocr_enabled: bool = True
    ocr_languages: str = "en"
    max_pdf_pages: int = Field(default=50, ge=1, le=500)
    max_image_width: int = Field(default=8000, ge=1, le=50000)
    max_image_height: int = Field(default=8000, ge=1, le=50000)
    max_image_pixels: int = Field(
        default=25_000_000,
        ge=1,
        le=500_000_000,
    )

    log_level: str = "INFO"

    fraud_model_path: Path = Path("models/fraud_model.joblib")
    training_data_path: Path = Path("data/raw/fraud_oracle.csv")
    vector_index_path: Path = Path("vector_store/policy.index")
    vector_metadata_path: Path = Path("vector_store/policy_chunks.json")

    cors_allowed_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls()

    @field_validator(
        "fraud_model_path",
        "training_data_path",
        "vector_index_path",
        "vector_metadata_path",
        mode="after",
    )
    @classmethod
    def resolve_paths(cls, value: Path) -> Path:
        return resolve_project_path(value)

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

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        origins = [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

        return origins


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
