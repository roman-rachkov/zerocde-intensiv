"""
Модуль для работы с SQLite базой данных.

Содержит функции для создания таблиц и сохранения сообщений.
"""

import sqlite3
import asyncio
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_path: str):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Создание таблицы messages, если она не существует."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    sender TEXT,
                    text TEXT,
                    date TEXT NOT NULL,
                    UNIQUE(id, chat_id)
                )
            ''')
            
            # Создаем индексы для быстрого поиска
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_id ON messages(chat_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_date ON messages(date)
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"База данных инициализирована: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    async def save_message(
        self,
        message_id: int,
        chat_id: int,
        sender: Optional[str],
        text: Optional[str],
        date: datetime
    ) -> bool:
        """
        Сохранение сообщения в базу данных с проверкой на дубликаты.
        
        Args:
            message_id: ID сообщения
            chat_id: ID чата
            sender: Имя отправителя
            text: Текст сообщения
            date: Дата и время сообщения
            
        Returns:
            True если сообщение сохранено, False если уже существует
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверяем, существует ли сообщение
            cursor.execute('''
                SELECT id FROM messages 
                WHERE id = ? AND chat_id = ?
            ''', (message_id, chat_id))
            
            if cursor.fetchone():
                conn.close()
                return False  # Сообщение уже существует
            
            # Сохраняем новое сообщение
            date_str = date.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO messages (id, chat_id, sender, text, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (message_id, chat_id, sender, text, date_str))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Дубликат (на случай race condition)
            return False
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")
            return False
    
    def get_message_count(self, chat_id: Optional[int] = None) -> int:
        """
        Получить количество сообщений в базе.
        
        Args:
            chat_id: ID чата (опционально, если None - все сообщения)
            
        Returns:
            Количество сообщений
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if chat_id:
                cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM messages')
            
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Ошибка при получении количества сообщений: {e}")
            return 0


