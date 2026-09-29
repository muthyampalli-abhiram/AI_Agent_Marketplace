import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        default_db_path = (BASE_DIR / "agent_marketplace.db").as_posix()
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{default_db_path}"
        )
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        self.GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.MAX_TEAM_SIZE: int = int(os.getenv("MAX_TEAM_SIZE", "8"))
        self.TASK_TIMEOUT_SECONDS: int = int(os.getenv("TASK_TIMEOUT_SECONDS", "60"))
        self.MAX_AGENT_RETRIES: int = int(os.getenv("MAX_AGENT_RETRIES", "1"))
        self.MIN_CAPABILITY_SCORE: float = float(os.getenv("MIN_CAPABILITY_SCORE", "0.35"))
        self.W_SUCCESS: float = float(os.getenv("W_SUCCESS", "0.4"))
        self.W_LATENCY: float = float(os.getenv("W_LATENCY", "0.2"))
        self.W_QUALITY: float = float(os.getenv("W_QUALITY", "0.4"))


settings = Settings()
