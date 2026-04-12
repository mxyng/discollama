FROM python:3.14.4-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

WORKDIR /mnt
COPY pyproject.toml poetry.lock .
RUN poetry config virtualenvs.create false && poetry install --no-root --only main

COPY . .
ENTRYPOINT ["python", "discollama.py"]
