#!/bin/sh
set -e

# Set defaults if variables not provided
export PORT=${PORT:-8000}
export URL=${URL:-sub}
export CLASH_URL=${CLASH_URL:-/clash}
export LOCAL_MODE=${LOCAL_MODE:-on}
export SUB_NAME=${SUB_NAME:-Aggregated}
export CONFIG_DIR=${CONFIG_DIR:-/app/configs}

mkdir -p "$CONFIG_DIR"

echo "Starting FastAPI on port $PORT"
echo "Configuration:"
echo "  URL: $URL"
echo "  CLASH_URL: $CLASH_URL"
echo "  LOCAL_MODE: $LOCAL_MODE"
echo "  SUB_NAME: $SUB_NAME"
echo "  CONFIG_DIR: $CONFIG_DIR"

# Run FastAPI
exec uvicorn main:app --host 0.0.0.0 --port $PORT
