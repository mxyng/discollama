FROM python:3.12.2-slim-bookworm

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

WORKDIR /mnt

# Copy only the files needed for the poetry installation to avoid cache invalidation
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --only main

# Copy the application
COPY . .

ENTRYPOINT ["poetry", "run", "python", "discollama.py"]
