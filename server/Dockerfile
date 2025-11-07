FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc build-essential libffi-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app

ENV WS_HOST=0.0.0.0
ENV WS_PORT=8080
ENV ALLOWED_ORIGINS=http://localhost:3000
ENV UPDATE_INTERVAL=2
ENV PUBLIC_HOST=localhost
ENV PUBLIC_PORT=8080
ENV USE_WSS=false

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--loop", "asyncio", "--ws", "websockets"]
