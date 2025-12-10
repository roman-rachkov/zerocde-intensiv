"""
Модуль для работы с GigaChat API.

Содержит функции для получения OAuth токена и генерации summary текста.
"""

import os
import requests
import logging
import urllib3
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Отключаем предупреждения о небезопасных SSL запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# URL endpoints GigaChat API
OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


class GigaChatError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAuthError(GigaChatError):
    """Ошибка аутентификации в GigaChat API."""
    pass


class GigaChatAPIError(GigaChatError):
    """Ошибка при запросе к GigaChat API."""
    pass


def get_access_token() -> str:
    """
    Получает OAuth токен для доступа к GigaChat API.
    
    Использует Basic Auth с CLIENT_ID и CLIENT_SECRET для получения access_token.
    Полученный токен затем используется в Bearer авторизации для API запросов.
    
    Returns:
        Access token (строка)
        
    Raises:
        GigaChatAuthError: При ошибке аутентификации
        GigaChatError: При других ошибках
    """
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise GigaChatAuthError(
            "CLIENT_ID и CLIENT_SECRET должны быть установлены в .env файле"
        )
    
    try:
        logger.info("Получение OAuth токена...")
        
        # Подготовка данных для запроса
        auth_data = {
            "scope": "GIGACHAT_API_PERS"
        }
        
        # Подготовка заголовков
        # RqUID должен быть равен client_id
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": client_id
        }
        
        # Отправка запроса с Basic Auth
        # Используем Basic Auth: Authorization: Basic <base64(client_id:client_secret)>
        # requests автоматически создаст заголовок Authorization с Basic Auth
        # verify=False отключает проверку SSL сертификата (для корпоративных прокси)
        response = requests.post(
            OAUTH_URL,
            data=auth_data,
            auth=(client_id, client_secret),
            headers=headers,
            timeout=30,
            verify=False
        )
        
        # Логируем детали ответа для отладки
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response body: {response.text}")
        
        if response.status_code == 200:
            try:
                token_data = response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    raise GigaChatAuthError("Токен не получен в ответе API")
                
                logger.info("OAuth токен успешно получен")
                return access_token
            except ValueError as e:
                error_msg = f"Ошибка парсинга JSON ответа: {response.text}"
                logger.error(error_msg)
                raise GigaChatAuthError(error_msg)
        else:
            # Пытаемся получить детальную информацию об ошибке
            try:
                error_json = response.json()
                error_message = error_json.get("message") or error_json.get("error_description") or error_json.get("error")
                error_code = error_json.get("code")
                
                if error_code:
                    error_detail = f"Code {error_code}: {error_message}" if error_message else f"Code {error_code}"
                else:
                    error_detail = error_message or response.text
            except:
                error_detail = response.text or "Нет деталей ошибки"
            
            # Формируем понятное сообщение об ошибке
            if response.status_code == 401:
                error_msg = (
                    f"Ошибка аутентификации (401): {error_detail}\n"
                    f"Проверьте правильность CLIENT_ID и CLIENT_SECRET в файле .env"
                )
            else:
                error_msg = f"Ошибка аутентификации: {response.status_code} - {error_detail}"
            
            logger.error(error_msg)
            raise GigaChatAuthError(error_msg)
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка при запросе токена: {str(e)}"
        logger.error(error_msg)
        raise GigaChatError(error_msg)
    except Exception as e:
        error_msg = f"Неожиданная ошибка при получении токена: {str(e)}"
        logger.error(error_msg)
        raise GigaChatError(error_msg)


def generate_summary(text: str) -> str:
    """
    Генерирует краткую выжимку (summary) текста с помощью GigaChat API.
    
    Args:
        text: Текст для обработки
        
    Returns:
        Краткая выжимка текста
        
    Raises:
        GigaChatAPIError: При ошибке запроса к API
        GigaChatError: При других ошибках
    """
    if not text or not text.strip():
        raise ValueError("Текст не может быть пустым")
    
    try:
        # Получаем токен доступа
        access_token = get_access_token()
        
        logger.info("Отправка запроса на генерацию summary...")
        
        # Подготовка данных для запроса
        request_data = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты – ассистент, который делает краткие выжимки текста."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        }
        
        # Отправка запроса с Bearer токеном
        # Используем Bearer Auth: Authorization: Bearer <access_token>
        # Токен получен через Basic Auth в get_access_token()
        # verify=False отключает проверку SSL сертификата (для корпоративных прокси)
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
            
            logger.info("Summary успешно сгенерирован")
            return summary.strip()
        else:
            error_msg = f"Ошибка API: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise GigaChatAPIError(error_msg)
            
    except GigaChatError:
        raise
    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка при запросе к API: {str(e)}"
        logger.error(error_msg)
        raise GigaChatAPIError(error_msg)
    except Exception as e:
        error_msg = f"Неожиданная ошибка при генерации summary: {str(e)}"
        logger.error(error_msg)
        raise GigaChatError(error_msg)

