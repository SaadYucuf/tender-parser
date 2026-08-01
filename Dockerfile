FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tashkent

WORKDIR /app

RUN useradd --system --create-home --shell /usr/sbin/nologin medtender

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chown -R medtender:medtender /app

USER medtender

CMD ["python", "-m", "app.main", "run"]
