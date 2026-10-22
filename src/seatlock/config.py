from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SeatLock"
    environment: Literal[
        "local", "test",
        "staging", "production"
    ] = "production"
    debug: bool = False

    database_url: str


settings = Settings()
