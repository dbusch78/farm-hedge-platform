FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[trading]"

COPY farm_platform/ ./farm_platform/
COPY backend/ ./backend/
COPY scripts/ ./scripts/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
