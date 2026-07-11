from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/incidents"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_api_token: str = ""
    jenkins_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()