"""
Основной модуль Telegram-бота на Telethon.

Реализует:
- Подключение к Telegram
- Получение списка диалогов
- Сбор последних N сообщений из чата
- Live-слушатель новых сообщений в реальном времени
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import User, Channel, Chat

# Add project root to the Python path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import config
from database import Database

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


class TelegramBot:
    """Класс для работы с Telegram через Telethon."""
    
    def __init__(self, db: Database):
        """Инициализация клиента Telethon."""
        self.client = TelegramClient(
            str(config.SESSION_PATH),
            config.API_ID,
            config.API_HASH
        )
        self.db = db
        self.is_running = False
    
    async def connect(self):
        """
        Подключение к Telegram с обработкой ошибок.
        
        Raises:
            Exception: При ошибке подключения
        """
        try:
            logger.info("Подключение к Telegram...")
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info("Не авторизован. Отправка кода...")
                phone = input('Введите номер телефона (с кодом страны, например +79991234567): ')
                await self.client.send_code_request(phone)
                
                code = input('Введите код, полученный в Telegram: ')
                try:
                    await self.client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input('Введите пароль двухфакторной аутентификации: ')
                    await self.client.sign_in(password=password)
            
            me = await self.client.get_me()
            logger.info(f"Успешно подключен как: {me.first_name} (@{me.username})")
            
        except FloodWaitError as e:
            logger.error(f"Превышен лимит запросов. Подождите {e.seconds} секунд")
            raise
        except Exception as e:
            logger.error(f"Ошибка при подключении: {e}")
            raise
    
    async def get_dialogs(self, limit: int = 20) -> List:
        """
        Получение списка доступных диалогов (чатов).
        
        Args:
            limit: Максимальное количество диалогов для получения
            
        Returns:
            Список диалогов
        """
        try:
            logger.info(f"Получение списка диалогов (лимит: {limit})...")
            dialogs = await self.client.get_dialogs(limit=limit)
            
            logger.info(f"Найдено {len(dialogs)} диалогов:")
            for i, dialog in enumerate(dialogs, 1):
                chat_title = dialog.name
                chat_id = dialog.id
                unread_count = dialog.unread_count
                logger.info(f"  {i}. {chat_title} (ID: {chat_id}, непрочитано: {unread_count})")
            
            return dialogs
        except Exception as e:
            logger.error(f"Ошибка при получении диалогов: {e}")
            return []
    
    async def get_chat_messages(
        self,
        chat_id: int,
        limit: int = 100
    ) -> List:
        """
        Сбор последних N сообщений из выбранного чата.
        
        Args:
            chat_id: ID чата
            limit: Количество сообщений для получения
            
        Returns:
            Список сообщений
        """
        try:
            logger.info(f"Получение последних {limit} сообщений из чата {chat_id}...")
            
            messages = []
            async for message in self.client.iter_messages(chat_id, limit=limit):
                messages.append(message)
                
                # Сохранение в базу данных
                sender_name = None
                if message.sender:
                    if isinstance(message.sender, User):
                        sender_name = f"{message.sender.first_name or ''} {message.sender.last_name or ''}".strip()
                        if not sender_name:
                            sender_name = message.sender.username or f"User {message.sender.id}"
                    elif isinstance(message.sender, (Channel, Chat)):
                        sender_name = message.sender.title
                
                text = message.message or "[медиа/файл]"
                
                saved = await self.db.save_message(
                    message_id=message.id,
                    chat_id=chat_id,
                    sender=sender_name,
                    text=text,
                    date=message.date
                )
                
                if saved:
                    logger.debug(f"Сохранено сообщение {message.id} из чата {chat_id}")
            
            logger.info(f"Получено и сохранено {len(messages)} сообщений из чата {chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из чата {chat_id}: {e}")
            return []
    
    async def setup_new_message_handler(self):
        """Настройка обработчика новых сообщений в реальном времени."""
        
        @self.client.on(events.NewMessage)
        async def handler(event):
            """Обработчик новых сообщений."""
            try:
                message = event.message
                chat = await event.get_chat()
                
                # Получаем информацию об отправителе
                sender_name = "Unknown"
                if message.sender:
                    sender = await message.get_sender()
                    if isinstance(sender, User):
                        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                        if not sender_name:
                            sender_name = sender.username or f"User {sender.id}"
                    elif isinstance(sender, (Channel, Chat)):
                        sender_name = sender.title
                
                # Получаем текст сообщения
                text = message.message or "[медиа/файл]"
                
                # Получаем название чата
                chat_title = chat.title if hasattr(chat, 'title') else (
                    f"{chat.first_name or ''} {chat.last_name or ''}".strip() 
                    if hasattr(chat, 'first_name') else f"Chat {chat.id}"
                )
                
                # Сохраняем в базу данных
                saved = await self.db.save_message(
                    message_id=message.id,
                    chat_id=chat.id,
                    sender=sender_name,
                    text=text,
                    date=message.date
                )
                
                if saved:
                    # Выводим короткий лог в консоль
                    print(f"[{chat_title}] {sender_name}: {text[:100]}")
                    logger.info(f"Новое сообщение сохранено: [{chat_title}] {sender_name}: {text[:100]}")
                else:
                    logger.debug(f"Сообщение {message.id} уже существует в базе")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке нового сообщения: {e}")
        
        logger.info("Обработчик новых сообщений настроен")
    
    async def start_listening(self):
        """Запуск live-слушателя новых сообщений."""
        if self.is_running:
            logger.warning("Слушатель уже запущен")
            return
        
        logger.info("Запуск live-слушателя новых сообщений...")
        self.is_running = True
        
        await self.setup_new_message_handler()
        await self.client.run_until_disconnected()
    
    async def disconnect(self):
        """Отключение от Telegram."""
        logger.info("Отключение от Telegram...")
        await self.client.disconnect()
        self.is_running = False


async def main():
    """Основная функция для запуска скрейпера."""
    logger.info("Инициализация скрейпера...")
    db_instance = Database(db_path=config.DB_PATH)
    bot = TelegramBot(db=db_instance)
    
    try:
        await bot.connect()
        
        print("\n=== Запуск live-слушателя ===")
        print("Ожидание новых сообщений... (Ctrl+C для остановки)")
        print("Формат вывода: [CHAT TITLE] sender: text\n")
        
        await bot.start_listening()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка в скрейпере: {e}")
    finally:
        await bot.disconnect()
        logger.info("Скрейпер завершил работу")

def run():
    # Проверка конфигурации
    if not config.API_ID or not config.API_HASH:
        print("ОШИБКА: Необходимо заполнить API_ID и API_HASH в config.py!")
        print("Получите их на https://my.telegram.org/apps")
        exit(1)
    
    # Запуск основной асинхронной функции
    asyncio.run(main())

if __name__ == '__main__':
    run()

