from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    financial_datasets_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
