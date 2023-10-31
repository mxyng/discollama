FROM python:3.11.6-alpine

RUN apk add --no-cache build-base libffi-dev
RUN pip install poetry

WORKDIR /mnt
COPY pyproject.toml poetry.lock .
RUN poetry install --no-root --only main

COPY . .
ENTRYPOINT ["poetry", "run", "python", "discollama.py"]
