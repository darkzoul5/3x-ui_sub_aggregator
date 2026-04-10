#!/bin/sh
set -e

# Set defaults if variables not provided
export PORT=${PORT:-8000}
export URL=${URL:-sub}
export LOCAL_MODE=${LOCAL_MODE:-on}
export FILE_PATH=${FILE_PATH:-/app/config.txt}

echo "Starting FastAPI on port $PORT"
echo "Configuration:"
echo "  URL: $URL"
echo "  LOCAL_MODE: $LOCAL_MODE"
echo "  FILE_PATH: $FILE_PATH"
echo ""

# Run FastAPI
exec uvicorn main:app --host 0.0.0.0 --port $PORT
