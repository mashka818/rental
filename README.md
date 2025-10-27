# RentalGuru Backend

Django REST API для платформы аренды транспорта RentalGuru.

## 🚀 Автоматический деплой

Проект настроен на автоматический деплой через GitHub Actions.

### Настройка GitHub Secrets

Перейдите в **Settings → Secrets and variables → Actions** и добавьте:

| Secret Name | Описание | Пример значения |
|-------------|----------|-----------------|
| `DOCKER_USERNAME` | Docker Hub username | `mashka818` |
| `DOCKER_TOKEN` | Docker Hub access token | Создайте на hub.docker.com |
| `SERVER_HOST` | IP адрес сервера | `147.45.138.96` |
| `SERVER_USER` | SSH пользователь | `root` |
| `SERVER_PASSWORD` | SSH пароль | `***` |

### Создание Docker Hub Token

1. Зайдите на https://hub.docker.com/settings/security
2. Нажмите **New Access Token**
3. Name: `GitHub Actions`
4. Permissions: `Read, Write, Delete`
5. Скопируйте токен и добавьте в GitHub Secrets

### Процесс деплоя

1. Сделайте изменения в коде
2. Закоммитьте и запушьте в `main` ветку
3. GitHub Actions автоматически:
   - Соберет Docker образы
   - Загрузит их на Docker Hub
   - Подключится к серверу
   - Обновит и перезапустит контейнеры
   - Выполнит миграции

## 📋 Исправленные баги

### v1.1.0 - 27.10.2025

- ✅ **Подсчет дней аренды**: Исправлена логика - с 23 по 24 число = 1 день
- ✅ **Валюта**: Исправлено название "Тайский Бат" 
- ✅ **Авторизация**: Добавлен автоматический возврат JWT токенов после регистрации
- ✅ **Безопасность**: Исправлены CORS и DEBUG настройки

## 🛠 Локальная разработка

### Требования

- Python 3.11+
- PostgreSQL 13+
- Redis

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/mashka818/rental.git
cd rental

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Копирование .env
cp .env.example .env
# Отредактируйте .env файл

# Миграции
python manage.py migrate

# Запуск сервера
python manage.py runserver
```

## 📁 Структура проекта

```
rental/
├── RentalGuru/          # Основной модуль Django
├── app/                 # Пользователи, аутентификация
├── chat/                # Чаты и заявки на аренду
├── vehicle/             # Транспортные средства
├── payment/             # Платежи (Tinkoff)
├── influencer/          # Инфлюенсеры и промокоды
├── franchise/           # Франшизы
├── manager/             # Менеджеры
├── notification/        # Push-уведомления
├── .github/workflows/   # CI/CD
└── deploy/              # Конфигурация для деплоя
```

## 🌐 API

- **Frontend**: https://rental-guru.netlify.app
- **Backend**: https://rentalguru.ru
- **Swagger**: https://rentalguru.ru/api/schema/swagger-ui/

## 📞 Контакты

- GitHub: [@mashka818](https://github.com/mashka818)
- Email: mariavoronuk122@gmail.com

