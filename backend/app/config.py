from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "sqlite:///../data/interview.db"
    max_daily_spend_usd: float = 5.0
    rapidapi_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"


settings = Settings()
