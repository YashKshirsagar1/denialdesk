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


settings = Settings()
