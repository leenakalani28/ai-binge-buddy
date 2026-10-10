import os
from dotenv import load_dotenv

load_dotenv()
TMDB_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_TOKEN = os.getenv("TMDB_BEARER_TOKEN", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
WEIGHTS = {"genre": 30, "content": 20, "language": 25, "streaming": 15}
