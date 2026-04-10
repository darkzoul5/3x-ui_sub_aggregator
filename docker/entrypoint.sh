#!/bin/sh
set -e

# Set defaults if variables not provided
export SERVER_NAME=${SERVER_NAME:-localhost}
export PORT=${PORT:-80}
export URL=${URL:-sub}
export SUB_NAME=${SUB_NAME:-unified links}
export LOCAL_MODE=${LOCAL_MODE:-on}
export FILE_PATH=${FILE_PATH:-/app/config.txt}

echo "Starting with configuration:"
echo "  SERVER_NAME: $SERVER_NAME"
echo "  PORT: $PORT"
echo "  URL: $URL"
echo "  SUB_NAME: $SUB_NAME"
echo "  LOCAL_MODE: $LOCAL_MODE"
echo "  FILE_PATH: $FILE_PATH"
echo ""

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
