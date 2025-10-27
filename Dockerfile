FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Копирование и установка прав на скрипты
RUN chmod +x entrypoint.sh start.sh

EXPOSE 8000 8001

ENTRYPOINT ["./entrypoint.sh"]
CMD ["./start.sh"]

