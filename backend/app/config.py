from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./assets.db"
    minio_endpoint: str = "localhost:9100"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "assets"
    vision_api_base_url: str = "http://114.113.151.16:8000/v1"
    vision_model: str = "Qwen3.5-35B-A3B"
    vision_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 250
    asr_model_size: str = "base"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
