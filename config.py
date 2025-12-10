"""
Unified configuration file for the Telegram Summarizer project.
"""

from pathlib import Path

# --- Project Structure ---
# Use pathlib to define paths relative to the project root
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# --- Database ---
DB_PATH = DATA_DIR / "telegram_messages.db"

# --- Telethon Scraper ---
# Get your credentials from https://my.telegram.org/apps
API_ID = 33567580  # Replace with your api_id
API_HASH = 'd6f0f2482f4735e42450efc5620af994'  # Replace with your api_hash
SESSION_NAME = 'telegram_session'
SESSION_PATH = DATA_DIR / SESSION_NAME

# --- Logging ---
LOG_PATH = DATA_DIR / "telegram_bot.log"

# --- Telegram Bot (pyTelegramBotAPI) ---
# Load from .env file at the project root
# Example .env content:
# BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
# GIGACHAT_CLIENT_ID=your_gigachat_client_id
# GIGACHAT_CLIENT_SECRET=your_gigachat_client_secret

# --- GigaChat ---
# Load from .env file at the project root
# GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET are expected