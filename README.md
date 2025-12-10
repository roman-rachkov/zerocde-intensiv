# Telegram Projects

Этот репозиторий содержит четыре независимых проекта для работы с Telegram и AI.

## Структура проекта

```
telegram/
├── telethon/          # Telegram-бот на Telethon
│   ├── main.py        # Основной файл с логикой Telethon
│   ├── db.py          # Работа с SQLite базой данных
│   ├── config.py      # Настройки (api_id, api_hash, session_name)
│   ├── requirements.txt
│   └── README.md      # Документация для Telethon проекта
│
├── ai/                # GigaChat Summary CLI
│   ├── main.py        # CLI-приложение
│   ├── gigachat.py    # Модуль для работы с GigaChat API
│   ├── utils.py       # Вспомогательные функции
│   ├── requirements.txt
│   ├── .env.example   # Пример конфигурации
│   └── README.md      # Документация для AI проекта
│
├── telebot_echo/      # Простой Echo-бот на pyTelegramBotAPI
│   ├── bot.py         # Основной файл бота
│   ├── requirements.txt
│   ├── .env.example   # Пример конфигурации
│   └── README.md      # Документация для Echo-бота
│
├── telebot_gigachat/  # Telegram-бот с GigaChat API
│   ├── bot.py         # Основной файл бота
│   ├── gigachat.py    # Модуль для работы с GigaChat API
│   ├── requirements.txt
│   ├── .env.example   # Пример конфигурации
│   └── README.md      # Документация для GigaChat бота
│
└── venv/              # Виртуальное окружение (общее)
```

## Проекты

### 1. Telethon Bot (`/telethon`)

Telegram-скрипт для сбора и мониторинга сообщений с использованием библиотеки Telethon.

**Основные возможности:**
- Подключение к Telegram через Telethon
- Получение списка диалогов
- Сбор последних N сообщений из чата
- Live-слушатель новых сообщений в реальном времени
- Сохранение в SQLite базу данных

**Документация:** См. [telethon/README.md](telethon/README.md)

### 2. GigaChat Summary CLI (`/ai`)

CLI-инструмент для получения кратких выжимок (summary) текста через GigaChat API.

**Основные возможности:**
- Получение summary из текстового файла
- Получение summary из строки текста
- Простой CLI-интерфейс
- Обработка ошибок API

**Документация:** См. [ai/README.md](ai/README.md)

### 3. Telegram Echo Bot (`/telebot_echo`)

Простой Telegram-бот на pyTelegramBotAPI с функцией echo (повторяет все сообщения пользователя).

**Основные возможности:**
- Повторяет все текстовые сообщения пользователя
- Команды `/start` и `/help`
- Простая структура кода

**Документация:** См. [telebot_echo/README.md](telebot_echo/README.md)

### 4. Telegram Bot с GigaChat API (`/telebot_gigachat`)

Telegram-бот на pyTelegramBotAPI с интеграцией GigaChat API для генерации ответов на вопросы.

**Основные возможности:**
- Отвечает на вопросы пользователей через GigaChat API
- Команды `/start`, `/help`, `/status`
- Обработка ошибок API
- Логирование операций

**Документация:** См. [telebot_gigachat/README.md](telebot_gigachat/README.md)

## Быстрый старт

### Telethon Bot

```bash
cd telethon
pip install -r requirements.txt
# Настройте config.py с вашими API credentials
python main.py
```

### GigaChat CLI

```bash
cd ai
pip install -r requirements.txt
# Создайте .env файл с CLIENT_ID и CLIENT_SECRET
python main.py summary --text "Ваш текст"
```

### Telegram Echo Bot

```bash
cd telebot_echo
pip install -r requirements.txt
# Создайте .env файл с BOT_TOKEN (получите у @BotFather)
python bot.py
```

### Telegram Bot с GigaChat API

```bash
cd telebot_gigachat
pip install -r requirements.txt
# Создайте .env файл с BOT_TOKEN, CLIENT_ID и CLIENT_SECRET
python bot.py
```

## Требования

- Python 3.7+ (для Telethon)
- Python 3.10+ (для GigaChat CLI)
- Виртуальное окружение (рекомендуется)

## Лицензия

Проекты созданы в образовательных целях.
