FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PYTHONPATH=/app/src \
    MCP_SCHEMA_SQL=/app/sql/003_mcp.sql

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY sql ./sql

EXPOSE 8000

CMD ["python", "-m", "ie_dados_mcp.server"]
