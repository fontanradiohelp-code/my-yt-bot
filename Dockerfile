# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем ffmpeg прямо в систему Linux
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Указываем рабочую папку
WORKDIR /app

# Копируем файлы проекта
COPY . .

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Команда для запуска бота
CMD ["python", "videos.py"]
