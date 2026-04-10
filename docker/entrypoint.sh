#!/bin/sh
set -e

# Substitute environment variables in nginx config template
envsubst '${SERVER_NAME},${PORT},${URL},${SUB_NAME}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start nginx in background
nginx -g 'daemon off;' &

# Capture nginx PID for cleanup
NGINX_PID=$!

# Function to cleanup and exit
cleanup() {
    echo "Shutting down..."
    kill $NGINX_PID 2>/dev/null || true
    exit 0
}

# Trap signals
trap cleanup SIGTERM SIGINT

# Run FastAPI in foreground
exec uvicorn main:app --host 0.0.0.0 --port 8000
