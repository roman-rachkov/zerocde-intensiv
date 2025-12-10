"""
Unified configuration file for the Telegram Summarizer project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file at the project root
# This allows all config variables to be loaded from one place
load_dotenv()

# --- Project Structure ---
# Use pathlib to define paths relative to the project root
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# --- Database ---
DB_PATH = DATA_DIR / "telegram_messages.db"

# --- Telethon Scraper ---
# Get your credentials from https://my.telegram.org/apps
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = 'telegram_session'
SESSION_PATH = DATA_DIR / SESSION_NAME

# --- Telegram Bot (pyTelegramBotAPI) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- GigaChat ---
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

# --- Logging ---
LOG_PATH = DATA_DIR / "telegram_bot.log"