FROM python:3.11-slim

# ffmpeg: para armar el video. fonts-noto-color-emoji: para los emojis a
# color en las tarjetas (el equivalente en Linux de la fuente de Windows).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render (y la mayoría de estos servicios) le asigna el puerto real a
# través de la variable de entorno PORT, no siempre es el mismo número.
ENV PORT=5000
EXPOSE 5000

CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1
