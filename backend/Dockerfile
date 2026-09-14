FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
    fastapi[standard]==0.115.4 \
    uvicorn[standard]==0.32.0 \
    asyncpg>=0.30.0 \
    sqlalchemy>=2.0.36 \
    alembic>=1.13.3 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.6.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4 \
    bcrypt>=4.2.0 \
    python-multipart>=0.0.12 \
    httpx>=0.27.2 \
    structlog>=24.4.0 \
    python-dotenv>=1.0.1 \
    email-validator>=2.2.0 \
    prometheus-client>=0.21.1

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]