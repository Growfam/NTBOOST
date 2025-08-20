# Dockerfile
FROM python:3.11-slim

# Встановлюємо системні залежності
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Створюємо робочу директорію
WORKDIR /app

# Копіюємо requirements і встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Створюємо директорію для логів
RUN mkdir -p logs

# Встановлюємо змінні середовища
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Відкриваємо порт
EXPOSE 8000

# Команда запуску
CMD ["python", "main.py"]