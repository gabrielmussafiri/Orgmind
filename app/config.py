from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")

    # ChromaDB
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")

    # App
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    APP_NAME: str = "OrgMind"
    VERSION: str = "1.0.0"

settings = Settings()