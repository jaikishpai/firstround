import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@postgres:5432/qa_platform",
        )
        self.secret_key = os.getenv("SECRET_KEY", "change-me")
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.allow_origins = os.getenv(
            "ALLOW_ORIGINS", "http://localhost:3001,http://localhost:3000"
        ).split(",")
        self.admin_seed_username = os.getenv("ADMIN_SEED_USERNAME", "")
        self.admin_seed_password = os.getenv("ADMIN_SEED_PASSWORD", "")


settings = Settings()

