FROM python:3.14-slim-bookworm

COPY . /app
WORKDIR /app

RUN apt update && \
    apt upgrade -y && \
    apt install -y wget curl && \
    pip install -r requirements.txt

EXPOSE 8000

# Granian workers
ENV GRANIAN_WORKERS=2
ENV GRANIAN_WORKERS_LIFETIME=86400
ENV GRANIAN_RESPAWN_FAILED_WORKERS=true

# Granian loop
ENV GRANIAN_LOOP=uvloop


ENTRYPOINT ["granian", "--interface", "asgi", "main:app", "--host", "0.0.0.0", "--port", "8000"]