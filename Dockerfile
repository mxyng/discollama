# Build stage
FROM python:3.12-alpine AS builder

RUN apk add --no-cache build-base libffi-dev
RUN pip install uv

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Runtime stage
FROM python:3.12-alpine

RUN addgroup -g 1001 -S appgroup && adduser -u 1001 -S appuser -G appgroup

WORKDIR /mnt

# Copy virtual environment from builder
COPY --from=builder /build/.venv /mnt/.venv

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appgroup /mnt

USER appuser

ENTRYPOINT ["/mnt/.venv/bin/uv", "run", "python", "main.py"]
