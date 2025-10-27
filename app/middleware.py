import json
import logging
import hashlib
import concurrent.futures
import re

from RentalGuru import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from mtranslate import translate

logger = logging.getLogger(__name__)


class TranslationMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.CACHE_TIMEOUT = getattr(settings, 'TRANSLATION_CACHE_TIMEOUT', 60 * 60 * 24)
        self.MAX_WORKERS = getattr(settings, 'TRANSLATION_MAX_WORKERS', 2)
        self.ERROR_KEYS = getattr(settings, 'TRANSLATION_ERROR_KEYS',
                                  ['detail', 'error', 'message', 'non_field_errors'])
        self.DRF_ERROR_LANGUAGE = getattr(settings, 'DRF_ERROR_LANGUAGE', 'en')

        self.timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}[tT]?\d{2}:\d{2}:\d{2}')
        self.iso_date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}[tT]?\d{2}:\d{2}:\d{2}(\.\d+)?([zZ]|[+-]\d{2}:?\d{2})?$')

        self.timestamp_fields = ['timestamp', 'created_at', 'updated_at', 'date', 'datetime',
                                 'time', 'created', 'modified', 'published_at', 'last_updated']

    def process_response(self, request, response):

        if not getattr(settings, 'TRANSLATION_ENABLED', True):
            return response

        if 'lang' not in request.GET:
            return response

        query_language = request.GET.get('lang')

        is_error_response = False
        if 'application/json' in response.get('Content-Type', ''):
            try:
                data = json.loads(response.content.decode('utf-8'))
                is_error_response = self._is_error_response(data, response.status_code)
            except Exception:
                pass

        if not query_language:

            if hasattr(request, 'user') and request.user.is_authenticated:
                user_language = getattr(request.user, 'language', None)
                target_language = getattr(user_language, 'code',
                                          settings.TRANSLATION_DEFAULT_LANGUAGE) if user_language else settings.TRANSLATION_DEFAULT_LANGUAGE
            else:
                target_language = settings.TRANSLATION_DEFAULT_LANGUAGE
        else:
            target_language = query_language

        if not target_language or (target_language == settings.TRANSLATION_DEFAULT_LANGUAGE and not is_error_response):
            return response

        if 'application/json' in response.get('Content-Type', ''):
            try:
                data = json.loads(response.content.decode('utf-8'))

                timestamp_replacements = {}
                self._protect_timestamps(data, timestamp_replacements)

                strings_to_translate = {}
                self._extract_translatable_strings(data, strings_to_translate, is_error=is_error_response)

                if strings_to_translate:
                    path_to_text = {path: text for path, text in strings_to_translate.items()}

                    source_language = self.DRF_ERROR_LANGUAGE if is_error_response else None

                    translated_strings = self._translate_strings(
                        path_to_text.values(),
                        target_language,
                        source_language=source_language
                    )

                    translated_data = self._apply_translations_by_path(data, path_to_text, translated_strings)
                else:
                    translated_data = data

                self._restore_timestamps(translated_data, timestamp_replacements)

                response.content = json.dumps(translated_data, ensure_ascii=False).encode('utf-8')
            except Exception as e:
                logger.error(f"Ошибка перевода JSON: {str(e)}")

        return response

    def _protect_timestamps(self, data, replacements, path=""):
        """Replace timestamp values with placeholders to protect them from translation"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key

                # If this is a timestamp field and the value is a string that looks like a timestamp
                if (key.lower() in self.timestamp_fields or self._is_timestamp(str(value))) and isinstance(value, str):
                    placeholder = f"__TIMESTAMP_{len(replacements)}__"
                    replacements[placeholder] = value
                    data[key] = placeholder
                else:
                    self._protect_timestamps(value, replacements, new_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                self._protect_timestamps(item, replacements, new_path)

    def _restore_timestamps(self, data, replacements):
        """Restore the original timestamp values from placeholders"""
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, str) and value.startswith("__TIMESTAMP_") and value.endswith("__"):
                    if value in replacements:
                        data[key] = replacements[value]
                else:
                    self._restore_timestamps(value, replacements)
        elif isinstance(data, list):
            for item in data:
                self._restore_timestamps(item, replacements)

    def _is_error_response(self, data, status_code):
        """Определяет, является ли ответ сообщением об ошибке"""
        if status_code >= 400:
            return True
        if isinstance(data, dict):
            return any(key in data for key in self.ERROR_KEYS)

        return False

    def _extract_translatable_strings(self, data, result, path="", is_error=False):
        """Извлекает все строки, которые нужно перевести"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key

                # Skip timestamp keys entirely
                if key.lower() in self.timestamp_fields:
                    continue

                error_field = is_error or key in self.ERROR_KEYS
                excluded_field = key in getattr(settings, 'TRANSLATION_EXCLUDED_FIELDS',
                                                ['date_joined', 'created_at', 'updated_at'])

                if error_field and isinstance(value, str) and value.strip() and not excluded_field:
                    if not self._is_timestamp(value) and not value.startswith("__TIMESTAMP_"):
                        result[new_path] = value
                elif not excluded_field:
                    self._extract_translatable_strings(value, result, new_path, error_field)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                self._extract_translatable_strings(item, result, new_path, is_error)

        elif isinstance(data, str) and (is_error or self._should_translate(data)):
            field_name = path.split('.')[-1] if '.' in path else path
            excluded_field = field_name in getattr(settings, 'TRANSLATION_EXCLUDED_FIELDS',
                                                   ['date_joined', 'created_at', 'updated_at'])

            if not excluded_field and not self._is_timestamp(data) and not data.startswith("__TIMESTAMP_"):
                result[path] = data

    def _is_timestamp(self, text):
        """Check if the string is a timestamp in ISO format or similar"""
        if not isinstance(text, str):
            return False

        # Check for ISO 8601 date format
        if self.iso_date_pattern.match(text):
            return True

        # More explicit check for common timestamp patterns
        if re.match(r'^\d{4}-\d{2}-\d{2}[Tt]?\d{2}:\d{2}:\d{2}', text.replace(" ", "")):
            return True

        # Check for other common timestamp formats
        return bool(self.timestamp_pattern.match(text.replace(" ", "")))

    def _apply_translations_by_path(self, data, path_to_text, translations):
        """Применяет переводы к данным по указанным путям"""
        result = data
        for path, text in path_to_text.items():
            if text in translations:
                components = self._parse_path(path)
                self._set_value_by_path(result, components, translations[text])

        return result

    def _parse_path(self, path):
        """Разбивает путь на компоненты"""
        components = []
        current = ""
        i = 0

        while i < len(path):
            if path[i] == '.':
                if current:
                    components.append(current)
                    current = ""
            elif path[i] == '[':
                if current:
                    components.append(current)
                    current = ""
                i += 1
                index = ""
                while i < len(path) and path[i] != ']':
                    index += path[i]
                    i += 1
                components.append(int(index))
            else:
                current += path[i]
            i += 1

        if current:
            components.append(current)

        return components

    def _set_value_by_path(self, data, components, value):
        """Устанавливает значение по пути"""
        if not components:
            return

        current = data
        for i, component in enumerate(components[:-1]):
            if isinstance(component, int):
                if i < len(components) - 1 and isinstance(components[i + 1], int):
                    if isinstance(current, list) and component < len(current):
                        current = current[component]
                    else:
                        return
                else:
                    if isinstance(current, list) and component < len(current):
                        current = current[component]
                    else:
                        return
            else:
                if isinstance(current, dict) and component in current:
                    current = current[component]
                else:
                    return

        last_component = components[-1]
        if isinstance(last_component, int):
            if isinstance(current, list) and last_component < len(current):
                current[last_component] = value
        else:
            if isinstance(current, dict) and last_component in current:
                current[last_component] = value

    def _should_translate(self, text):
        """Определяет, нужно ли переводить текст"""
        if not isinstance(text, str) or not text.strip():
            return False

        EXCLUDED_KEYWORDS = getattr(settings, 'TRANSLATION_EXCLUDED_KEYWORDS',
                                    ['code', 'url', 'slug', 'id', 'price', 'year', 'latitude', 'longitude', 'rating',
                                     'date_joined', 'timestamp',
                                     'email', 'phone', 'http://', 'https://', 'language'])

        # Check if this might be a currency code (3 characters, all uppercase)
        if len(text) == 3 and text.upper() == text:
            return False

        if len(text.strip()) <= 2:
            return False

        LANGUAGE_CODES = getattr(settings, 'TRANSLATION_EXCLUDED_LANGUAGE_CODES',
                                 ['EN', 'RU', 'FR', 'DE', 'ES', 'IT', 'CN', 'JP', 'AR', 'UK'])
        if text.upper() in LANGUAGE_CODES:
            return False

        if text.startswith(('http://', 'https://')) or text.strip().isdigit():
            return False

        # Skip timestamps and placeholders
        if self._is_timestamp(text) or text.startswith("__TIMESTAMP_"):
            return False

        return not any(keyword in text.lower() for keyword in EXCLUDED_KEYWORDS)

    def _translate_strings(self, strings_to_translate, target_language, source_language=None):
        """Переводит строки и кеширует результат"""
        translated_strings = {}
        unique_strings = set(strings_to_translate)

        for text in unique_strings:
            if text is None:
                continue

            source_lang_part = f"_{source_language}" if source_language else ""
            cache_key = f"trans{source_lang_part}_{target_language}_{hashlib.md5(text.encode()).hexdigest()}"
            cached_translation = cache.get(cache_key)

            if cached_translation:
                translated_strings[text] = cached_translation
            else:
                try:
                    if source_language:
                        translated_text = translate(text, target_language)
                    else:
                        translated_text = translate(text, target_language)

                    if not translated_text.strip():
                        logger.warning(f"Пустой перевод для: '{text}'")
                        translated_text = text

                    translated_strings[text] = translated_text
                    cache.set(cache_key, translated_text, self.CACHE_TIMEOUT)
                except Exception as e:
                    logger.error(f"Ошибка перевода '{text}': {str(e)}")
                    translated_strings[text] = text

        return translated_strings
