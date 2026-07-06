import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def resolve_project_file(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner").strip()
DEEPSEEK_BASE_URL = os.getenv(
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com",
).strip()

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017/",
).strip()
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "validiiz").strip()
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
)
INBOUND_REPLIES_COLLECTION = os.getenv(
    "INBOUND_REPLIES_COLLECTION",
    "inbound_replies",
).strip()

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()
GOOGLE_OAUTH_CREDENTIALS_FILE = resolve_project_file(
    os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "credentials.json")
)
GOOGLE_OAUTH_TOKEN_FILE = resolve_project_file(
    os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json")
)

CALENDAR_TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "Asia/Karachi").strip()
CALENDAR_SLOT_MINUTES = int(os.getenv("CALENDAR_SLOT_MINUTES", "30"))
CALENDAR_SEARCH_DAYS = int(os.getenv("CALENDAR_SEARCH_DAYS", "14"))

if not DEEPSEEK_API_KEY:
    raise ValueError(
        "DEEPSEEK_API_KEY is missing. Add it to this workflow folder's .env file."
    )

if CALENDAR_SLOT_MINUTES <= 0:
    raise ValueError("CALENDAR_SLOT_MINUTES must be greater than 0.")

if CALENDAR_SEARCH_DAYS <= 0:
    raise ValueError("CALENDAR_SEARCH_DAYS must be greater than 0.")

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

mongo_client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=MONGODB_SERVER_SELECTION_TIMEOUT_MS,
)

mongo_database = mongo_client[MONGODB_DATABASE]
inbound_replies_collection = mongo_database[INBOUND_REPLIES_COLLECTION]
