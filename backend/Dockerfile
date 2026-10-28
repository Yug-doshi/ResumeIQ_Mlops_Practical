
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip --timeout 120 --retries 10 && \
    python -m pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY app ./app
COPY config ./config
COPY mlops ./mlops

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
