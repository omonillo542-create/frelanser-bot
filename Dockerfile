FROM python:3.11-slim

WORKDIR /app

# Faqat kutubxonalar (build tez)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodni nusxalash
COPY bot ./bot

ENV PYTHONUNBUFFERED=1

# Bot 24/7 ishlaydi (worker — render'da hech qachon uyqutmaga tushmaydi)
CMD ["python", "bot/main.py"]
