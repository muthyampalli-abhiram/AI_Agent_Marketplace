import os
from pathlib import Path
from dotenv import load_dotenv

print("Current working directory:", os.getcwd())
print("Does .env exist at cwd?", Path(".env").exists())
print("Does .env exist next to config.py's expected location?",
      Path(__file__).resolve().parent.joinpath(".env").exists())

load_dotenv()
print("GROQ_API_KEY from os.environ after load_dotenv():",
      repr(os.getenv("GROQ_API_KEY")))

from app.config import settings
print("settings.GROQ_API_KEY:", repr(settings.GROQ_API_KEY))
print("settings.GROQ_MODEL:", repr(settings.GROQ_MODEL))
