"""
Telegram-бот с интеграцией GigaChat API для суммаризации сообщений.
"""
import telebot
import os
import sqlite3
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
import urllib3

# Add project root to the Python path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import config
from llm.gigachat import get_access_token, CHAT_COMPLETIONS_URL, GigaChatError, GigaChatAuthError, GigaChatAPIError

# Load .env file from the project root
load_dotenv(dotenv_path=config.BASE_DIR / ".env")

# Отключаем предупреждения о небезопасных SSL запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    print("Убедитесь, что:")
    print("1. Файл .env существует в корневой директории проекта")
    print("2. В файле .env указан BOT_TOKEN=ваш_токен")
    raise ValueError("BOT_TOKEN должен быть установлен в .env файле")

# Проверяем формат токена (должен содержать двоеточие)
if ":" not in BOT_TOKEN:
    print("ОШИБКА: Неверный формат токена!")
    print("Токен должен содержать двоеточие (например: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
    raise ValueError("Неверный формат токена. Токен должен содержать двоеточие")

# Путь к базе данных из конфига
DB_PATH = config.DB_PATH

# Создаем экземпляр бота
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info(f"Бот инициализирован успешно (токен: {BOT_TOKEN[:10]}...)")
    logger.info(f"База данных: {DB_PATH}")
except Exception as e:
    logger.error(f"ОШИБКА при создании бота: {e}")
    print("Проверьте правильность токена в файле .env")
    raise


def init_database():
    """Инициализация базы данных - добавляет поле summarized и таблицу summaries."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем, есть ли колонка summarized
        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'summarized' not in columns:
            logger.info("Добавление колонки 'summarized' в таблицу messages...")
            cursor.execute('''
                ALTER TABLE messages ADD COLUMN summarized INTEGER DEFAULT 0
            ''')
            conn.commit()
            logger.info("Колонка 'summarized' успешно добавлена")
        
        # Создаем индекс для быстрого поиска необработанных сообщений
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_summarized ON messages(summarized)
        ''')
        
        # Создаем таблицу для хранения суммаризаций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                summary_text TEXT NOT NULL,
                message_ids TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Создаем индексы для таблицы summaries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_summaries_chat_id ON summaries(chat_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_summaries_created_at ON summaries(created_at)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def get_new_messages(chat_id: int = None) -> list:
    """
    Получает все новые (не суммаризированные) сообщения из базы данных.
    
    Args:
        chat_id: ID чата (опционально, если None - все чаты)
        
    Returns:
        Список кортежей (id, chat_id, sender, text, date)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if chat_id:
            cursor.execute('''
                SELECT id, chat_id, sender, text, date 
                FROM messages 
                WHERE summarized = 0 AND chat_id = ?
                ORDER BY date ASC
            ''', (chat_id,))
        else:
            cursor.execute('''
                SELECT id, chat_id, sender, text, date 
                FROM messages 
                WHERE summarized = 0
                ORDER BY date ASC
            ''')
        
        messages = cursor.fetchall()
        conn.close()
        
        logger.info(f"Найдено {len(messages)} новых сообщений для суммаризации")
        return messages
    except Exception as e:
        logger.error(f"Ошибка при получении новых сообщений: {e}")
        return []


def save_summary(chat_id: int, summary_text: str, message_ids: list):
    """
    Сохраняет суммаризацию в базу данных и отмечает сообщения как обработанные.
    
    Args:
        chat_id: ID чата (может быть None для всех чатов)
        summary_text: Текст суммаризации
        message_ids: Список ID сообщений, которые были суммаризированы
    """
    if not message_ids:
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        from datetime import datetime
        
        # Сохраняем суммаризацию
        message_ids_str = ','.join(map(str, message_ids))
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO summaries (chat_id, summary_text, message_ids, message_count, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, summary_text, message_ids_str, len(message_ids), created_at))
        
        # Отмечаем сообщения как обработанные
        placeholders = ','.join('?' * len(message_ids))
        cursor.execute(f'''
            UPDATE messages 
            SET summarized = 1 
            WHERE id IN ({placeholders})
        ''', message_ids)
        
        conn.commit()
        conn.close()
        logger.info(f"Суммаризация сохранена: {len(message_ids)} сообщений, chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении суммаризации: {e}")
        raise


def generate_summary_chunked(text: str, chunk_size: int = 30000) -> str:
    """
    Генерирует summary для длинного текста, разбивая его на части.
    
    Args:
        text: Текст для суммаризации
        chunk_size: Размер части текста
        
    Returns:
        Объединенная выжимка всех частей
    """
    logger.info(f"Разбиваю текст на части (размер части: {chunk_size})")
    
    # Разбиваем текст на части по абзацам для лучшей структуры
    chunks = []
    current_chunk = ""
    
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 <= chunk_size:
            current_chunk += paragraph + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # Если один абзац больше chunk_size, разбиваем его по предложениям
            if len(paragraph) > chunk_size:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 <= chunk_size:
                        current_chunk += sentence + '. '
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + '. '
            else:
                current_chunk = paragraph + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    logger.info(f"Текст разбит на {len(chunks)} частей")
    
    # Генерируем summary для каждой части
    summaries = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Обрабатываю часть {i}/{len(chunks)} ({len(chunk)} символов)...")
        try:
            # Используем рекурсивный вызов generate_summary, но с меньшим max_length
            chunk_summary = generate_summary(chunk, max_length=chunk_size)
            summaries.append(chunk_summary)
        except Exception as e:
            logger.error(f"Ошибка при обработке части {i}: {e}")
            summaries.append(f"[Часть {i}: ошибка обработки]")
    
    # Если получили несколько summary, объединяем их в финальную выжимку
    if len(summaries) > 1:
        logger.info("Объединяю summary частей в финальную выжимку...")
        combined_summaries = "\n\n".join([f"Часть {i+1}:\n{s}" for i, s in enumerate(summaries)])
        # Создаем финальную выжимку из объединенных summary
        try:
            final_summary = generate_summary(combined_summaries, max_length=chunk_size)
            return final_summary
        except Exception as e:
            logger.warning(f"Не удалось создать финальную выжимку, возвращаю объединенные части: {e}")
            return "\n\n".join([f"Часть {i+1}:\n{s}" for i, s in enumerate(summaries)])
    else:
        return summaries[0] if summaries else "Не удалось создать выжимку"


def generate_summary(text: str, max_length: int = 30000) -> str:
    """
    Генерирует краткую выжимку текста через GigaChat API.
    
    Args:
        text: Текст для суммаризации
        max_length: Максимальная длина текста для одного запроса (по умолчанию 50000)
        
    Returns:
        Краткая выжимка текста
    """
    try:
        # Если текст слишком длинный, разбиваем на части
        if len(text) > max_length:
            logger.info(f"Текст слишком длинный ({len(text)} символов), разбиваю на части...")
            return generate_summary_chunked(text, max_length)
        
        # Получаем токен доступа
        access_token = get_access_token()
        
        logger.info("Отправка запроса на генерацию summary...")
        
        # Улучшенный промпт для избежания ограничений
        system_prompt = (
            "Ты – профессиональный ассистент для создания кратких выжимок текста. "
            "Твоя задача - проанализировать предоставленный текст и создать информативную выжимку, "
            "выделяя основные темы, ключевые моменты и важную информацию. "
            "Отвечай только на основе предоставленного текста, избегая общих фраз и ограничений. "
            "Создай конкретную и полезную выжимку."
        )
        
        user_prompt = (
            "Проанализируй следующий текст и создай краткую информативную выжимку, "
            "выделяя основные темы и ключевые моменты:\n\n"
            f"{text}"
        )
        
        # Подготовка данных для запроса
        request_data = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        # Отправка запроса с Bearer токеном
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            json=request_data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=60,
            verify=False
        )
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Извлекаем ответ из структуры ответа GigaChat
            choices = response_data.get("choices", [])
            if not choices:
                raise GigaChatAPIError("Пустой ответ от API")
            
            summary = choices[0].get("message", {}).get("content", "")
            
            if not summary:
                raise GigaChatAPIError("Summary не получен в ответе API")
            
            # Проверяем, не является ли ответ сообщением об ограничении
            summary_lower = summary.lower()
            restriction_keywords = [
                "ограничен", "ограничены", "временно ограничены",
                "некорректные ответы", "чувствительные темы",
                "благодарим за понимание", "избежание неправильного толкования"
            ]
            
            if any(keyword in summary_lower for keyword in restriction_keywords):
                logger.warning("Получен ответ об ограничении от GigaChat API")
                raise GigaChatAPIError(
                    "GigaChat API вернул ограничение. Попробуйте разбить запрос на меньшие части "
                    "или использовать команду /summary_chat для конкретного чата."
                )
            
            logger.info("Summary успешно сгенерирован")
            return summary.strip()
        else:
            error_msg = f"Ошибка API: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise GigaChatAPIError(error_msg)
            
    except (GigaChatError, GigaChatAPIError):
        raise
    except Exception as e:
        error_msg = f"Неожиданная ошибка при генерации summary: {str(e)}"
        logger.error(error_msg)
        raise GigaChatError(error_msg)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Обработчик команд /start и /help.
    """
    welcome_text = (
        "Привет! 👋\n\n"
        "Я бот для суммаризации сообщений из базы данных.\n\n"
        "Команды:\n"
        "/start или /help - показать это сообщение\n"
        "/summary - создать выжимку из всех новых сообщений\n"
        "/summary_chat <chat_id> - создать выжимку для конкретного чата\n"
        "/status - проверить статус подключения к GigaChat API\n"
        "/stats - показать статистику по базе данных\n"
        "/history - показать последние суммаризации"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['status'])
def check_status(message):
    """
    Проверка статуса подключения к GigaChat API.
    """
    try:
        bot.reply_to(message, "Проверяю подключение к GigaChat API...")
        
        # Пробуем получить токен для проверки подключения
        token = get_access_token()
        
        if token:
            bot.reply_to(
                message,
                "✅ Подключение к GigaChat API работает!\n\n"
                "Можете использовать команду /summary для суммаризации."
            )
        else:
            bot.reply_to(message, "❌ Не удалось получить токен доступа")
            
    except GigaChatAuthError as e:
        bot.reply_to(
            message,
            f"❌ Ошибка аутентификации:\n{str(e)}\n\n"
            "Проверьте CLIENT_ID и CLIENT_SECRET в файле .env"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['stats'])
def show_stats(message):
    """
    Показать статистику по базе данных.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Общее количество сообщений
        cursor.execute('SELECT COUNT(*) FROM messages')
        total = cursor.fetchone()[0]
        
        # Количество новых (не суммаризированных) сообщений
        cursor.execute('SELECT COUNT(*) FROM messages WHERE summarized = 0')
        new = cursor.fetchone()[0]
        
        # Количество обработанных сообщений
        cursor.execute('SELECT COUNT(*) FROM messages WHERE summarized = 1')
        processed = cursor.fetchone()[0]
        
        # Количество уникальных чатов
        cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM messages')
        chats = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = (
            "📊 Статистика базы данных:\n\n"
            f"Всего сообщений: {total}\n"
            f"Новых (не обработанных): {new}\n"
            f"Обработанных: {processed}\n"
            f"Уникальных чатов: {chats}"
        )
        
        bot.reply_to(message, stats_text)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении статистики: {str(e)}")


@bot.message_handler(commands=['summary'])
def summarize_all(message):
    """
    Создать выжимку из всех новых сообщений.
    """
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Получаем все новые сообщения
        new_messages = get_new_messages()
        
        if not new_messages:
            bot.reply_to(
                message,
                "✅ Новых сообщений для суммаризации нет.\n\n"
                "Все сообщения уже обработаны."
            )
            return
        
        # Формируем текст из всех новых сообщений
        messages_text = []
        message_ids = []
        
        for msg_id, chat_id, sender, text, date in new_messages:
            if text and text.strip() and text != "[медиа/файл]":
                messages_text.append(f"[{date}] {sender}: {text}")
                message_ids.append(msg_id)
        
        if not messages_text:
            bot.reply_to(
                message,
                "❌ Не найдено текстовых сообщений для суммаризации.\n\n"
                "Все сообщения содержат только медиа или файлы."
            )
            return
        
        # Объединяем все сообщения в один текст
        combined_text = "\n\n".join(messages_text)
        
        # Предупреждение при большом количестве сообщений
        warning_text = ""
        if len(message_ids) > 100:
            warning_text = (
                f"\n⚠️ Внимание: Очень много сообщений ({len(message_ids)}). "
                f"Это может занять больше времени или вызвать ограничения API.\n"
                f"Рекомендуется использовать /summary_chat для конкретного чата.\n\n"
            )
        
        bot.reply_to(
            message,
            f"📝 Найдено {len(message_ids)} новых сообщений.{warning_text}"
            f"Генерирую выжимку...\n\n"
            f"Это может занять некоторое время."
        )
        
        # Генерируем summary
        summary = generate_summary(combined_text)
        
        # Сохраняем суммаризацию в базу данных и отмечаем сообщения как обработанные
        save_summary(chat_id=None, summary_text=summary, message_ids=message_ids)
        
        # Отправляем результат
        result_text = (
            f"📋 Выжимка из {len(message_ids)} сообщений:\n\n"
            f"{summary}"
        )
        
        # Разбиваем на части, если сообщение слишком длинное (лимит Telegram - 4096 символов)
        if len(result_text) > 4000:
            # Отправляем первую часть
            bot.reply_to(message, result_text[:4000])
            # Отправляем остальное
            remaining = result_text[4000:]
            while len(remaining) > 4000:
                bot.send_message(message.chat.id, remaining[:4000])
                remaining = remaining[4000:]
            if remaining:
                bot.send_message(message.chat.id, remaining)
        else:
            bot.reply_to(message, result_text)
        
        logger.info(f"Суммаризация завершена для {len(message_ids)} сообщений")
        
    except GigaChatAuthError as e:
        error_msg = (
            "❌ Ошибка аутентификации в GigaChat API\n\n"
            f"{str(e)}\n\n"
            "Проверьте настройки CLIENT_ID и CLIENT_SECRET в файле .env"
        )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка аутентификации: {e}")
        
    except GigaChatAPIError as e:
        error_str = str(e)
        # Проверяем, является ли это ограничением
        if "ограничение" in error_str.lower() or "ограничен" in error_str.lower():
            error_msg = (
                "⚠️ GigaChat API вернул ограничение для этого запроса.\n\n"
                "Попробуйте:\n"
                "1. Использовать /summary_chat <chat_id> для конкретного чата (меньше сообщений)\n"
                "2. Подождать некоторое время и попробовать снова\n"
                "3. Разбить запрос на части вручную"
            )
        else:
            error_msg = (
                "❌ Ошибка при запросе к GigaChat API\n\n"
                f"{error_str}\n\n"
                "Попробуйте позже или проверьте подключение к интернету."
            )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка API: {e}")
        
    except GigaChatError as e:
        error_msg = (
            "❌ Ошибка GigaChat\n\n"
            f"{str(e)}"
        )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка GigaChat: {e}")
        
    except Exception as e:
        error_msg = (
            "❌ Произошла неожиданная ошибка\n\n"
            f"{str(e)}"
        )
        bot.reply_to(message, error_msg)
        logger.exception("Неожиданная ошибка при суммаризации")


@bot.message_handler(commands=['summary_chat'])
def summarize_chat(message):
    """
    Создать выжимку для конкретного чата.
    Использование: /summary_chat <chat_id>
    """
    try:
        # Парсим команду
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ Не указан chat_id.\n\n"
                "Использование: /summary_chat <chat_id>\n\n"
                "Пример: /summary_chat 123456789"
            )
            return
        
        try:
            chat_id = int(parts[1])
        except ValueError:
            bot.reply_to(message, "❌ chat_id должен быть числом")
            return
        
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Получаем новые сообщения для конкретного чата
        new_messages = get_new_messages(chat_id=chat_id)
        
        if not new_messages:
            bot.reply_to(
                message,
                f"✅ Новых сообщений для чата {chat_id} нет.\n\n"
                "Все сообщения уже обработаны."
            )
            return
        
        # Формируем текст из всех новых сообщений
        messages_text = []
        message_ids = []
        
        for msg_id, msg_chat_id, sender, text, date in new_messages:
            if text and text.strip() and text != "[медиа/файл]":
                messages_text.append(f"[{date}] {sender}: {text}")
                message_ids.append(msg_id)
        
        if not messages_text:
            bot.reply_to(
                message,
                f"❌ Не найдено текстовых сообщений для чата {chat_id}."
            )
            return
        
        # Объединяем все сообщения в один текст
        combined_text = "\n\n".join(messages_text)
        
        bot.reply_to(
            message,
            f"📝 Найдено {len(message_ids)} новых сообщений в чате {chat_id}.\n"
            f"Генерирую выжимку...\n\n"
            f"Это может занять некоторое время."
        )
        
        # Генерируем summary
        summary = generate_summary(combined_text)
        
        # Сохраняем суммаризацию в базу данных и отмечаем сообщения как обработанные
        save_summary(chat_id=chat_id, summary_text=summary, message_ids=message_ids)
        
        # Отправляем результат
        result_text = (
            f"📋 Выжимка из {len(message_ids)} сообщений (чат {chat_id}):\n\n"
            f"{summary}"
        )
        
        # Разбиваем на части, если сообщение слишком длинное
        if len(result_text) > 4000:
            bot.reply_to(message, result_text[:4000])
            remaining = result_text[4000:]
            while len(remaining) > 4000:
                bot.send_message(message.chat.id, remaining[:4000])
                remaining = remaining[4000:]
            if remaining:
                bot.send_message(message.chat.id, remaining)
        else:
            bot.reply_to(message, result_text)
        
        logger.info(f"Суммаризация завершена для чата {chat_id}: {len(message_ids)} сообщений")
        
    except GigaChatAuthError as e:
        error_msg = (
            "❌ Ошибка аутентификации в GigaChat API\n\n"
            f"{str(e)}\n\n"
            "Проверьте настройки CLIENT_ID и CLIENT_SECRET в файле .env"
        )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка аутентификации: {e}")
        
    except GigaChatAPIError as e:
        error_str = str(e)
        # Проверяем, является ли это ограничением
        if "ограничение" in error_str.lower() or "ограничен" in error_str.lower():
            error_msg = (
                "⚠️ GigaChat API вернул ограничение для этого запроса.\n\n"
                "Попробуйте:\n"
                "1. Использовать другой chat_id с меньшим количеством сообщений\n"
                "2. Подождать некоторое время и попробовать снова\n"
                "3. Проверить содержимое сообщений в чате"
            )
        else:
            error_msg = (
                "❌ Ошибка при запросе к GigaChat API\n\n"
                f"{error_str}\n\n"
                "Попробуйте позже или проверьте подключение к интернету."
            )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка API: {e}")
        
    except GigaChatError as e:
        error_msg = (
            "❌ Ошибка GigaChat\n\n"
            f"{str(e)}"
        )
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка GigaChat: {e}")
        
    except Exception as e:
        error_msg = (
            "❌ Произошла неожиданная ошибка\n\n"
            f"{str(e)}"
        )
        bot.reply_to(message, error_msg)
        logger.exception("Неожиданная ошибка при суммаризации")


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """
    Обработчик всех остальных сообщений.
    """
    bot.reply_to(
        message,
        "Я понимаю только команды.\n\n"
        "Используйте /help для списка доступных команд."
    )


def run():
    """Запускает бота."""
    logger.info("Инициализация бота...")
    try:
        init_database()
    except Exception as e:
        logger.error(f"ОШИБКА при инициализации базы данных: {e}")
        logger.error(f"Убедитесь, что база данных существует по пути: {DB_PATH}")
        raise

    logger.info(f"База данных: {DB_PATH}")
    logger.info("Бот запускается...")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\nБот остановлен")
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка при работе бота: {e}")

if __name__ == '__main__':
    run()
