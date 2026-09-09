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
    embedding_api_base_url: str = "http://114.113.151.16:8003/v1"
    embedding_model: str = "Qwen3-Embedding-8B"
    embedding_api_key: str = ""
    embedding_dimension: int = 4096
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "assets_qwen3_embedding_8b_v1"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 250
    pexels_api_key: str = ""
    pexels_api_base_url: str = "https://api.pexels.com"
    pixabay_api_key: str = ""
    pixabay_api_base_url: str = "https://pixabay.com"
    unsplash_access_key: str = ""
    unsplash_api_base_url: str = "https://api.unsplash.com"
    openverse_api_base_url: str = "https://api.openverse.org/v1"
    ibaotu_id_token: str = ""
    ibaotu_max_download_mb: int = 1024
    fred_api_key: str = ""
    fred_api_base_url: str = "https://api.stlouisfed.org/fred"
    asr_model_size: str = "base"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
