FROM python:3.13-alpine

RUN mkdir -p /app

WORKDIR /app

# Copy application dependencies and code
COPY app/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app/main.py /app/
COPY app/configs /app/configs

# Copy and setup entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Health check - check FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Start the application via entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
