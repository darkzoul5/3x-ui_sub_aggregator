#!/bin/sh
set -e

# Set defaults if variables not provided
export PORT=${PORT:-8000}
export URL=${URL}
export CLASH_URL=${CLASH_URL}
export LOCAL_MODE=${LOCAL_MODE:-on}
export SUB_NAME=${SUB_NAME:-Aggregated}
export CONFIG_DIR=${CONFIG_DIR:-/app/configs}
export LOG_LEVEL=${LOG_LEVEL:-info}

mkdir -p "$CONFIG_DIR"

echo "Starting FastAPI on port $PORT"
echo "Configuration:"
if [ -n "$URL" ]; then
	echo "  URL: $URL"
else
	echo "  URL: <disabled>"
fi
if [ -n "$CLASH_URL" ]; then
	echo "  CLASH_URL: $CLASH_URL"
else
	echo "  CLASH_URL: <disabled>"
fi
echo "  LOCAL_MODE: $LOCAL_MODE"
echo "  SUB_NAME: $SUB_NAME"
echo "  CONFIG_DIR: $CONFIG_DIR"
echo "  LOG_LEVEL: $LOG_LEVEL"

# Run FastAPI
exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level "$LOG_LEVEL"
