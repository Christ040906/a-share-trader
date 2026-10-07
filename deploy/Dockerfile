FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY mcp/ /app/mcp/
RUN pip install --upgrade pip && pip install /app/mcp

ENV MCP_HOST=0.0.0.0 \
    MARKET_DATA_PROVIDER_ORDER=akshare,tushare \
    ENABLE_SNAPSHOT_WORKER=true \
    SNAPSHOT_INTERVAL_SECONDS=300 \
    SNAPSHOT_DB_PATH=/data/ashare_snapshots.sqlite3

CMD ["ashare-realtime-mcp"]
