FROM python:3.10

WORKDIR /app

# Копируем и устанавливаем зависимости отдельно для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код
COPY . .

# Запускаем бота
CMD ["python", "main.py"]
