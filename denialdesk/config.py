from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost/denialdesk"
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"

    # Auth settings
    dev_mode: bool = True
    dev_jwt_secret: str = "dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    auth0_domain: str = ""
    auth0_audience: str = ""

    # Self-serve signup creates a practice + clinic_admin. The practice stays locked
    # (no uploads) until an ops admin marks the BAA + service agreement signed.
    allow_signup: bool = True
    access_token_ttl_hours: int = 8

    # Built frontend (vite build output). Served by the API when present.
    frontend_dist: str = "frontend/dist"

    # CORS — restrict in production. Comma-separated list of allowed origins.
    # Dev default: localhost only. Prod: set to the actual frontend domain.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"


settings = Settings()
