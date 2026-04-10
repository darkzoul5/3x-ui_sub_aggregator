FROM python:3.13-alpine

# Install nginx and gettext for environment variable substitution
RUN apk add --no-cache \
    nginx \
    gettext

# Create necessary directories
RUN mkdir -p /app /etc/nginx/ssl

WORKDIR /app

# Copy application dependencies and code
COPY app/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app/main.py /app/

# Copy nginx configuration template
COPY docker/nginx.conf.template /etc/nginx/

# Copy and setup entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports
EXPOSE 8000 ${PORT:-443}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/', timeout=5)" || exit 1

# Start the application via entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
