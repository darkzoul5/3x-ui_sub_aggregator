#!/bin/sh
set -e

# Set defaults if variables not provided
export PORT=${PORT:-8000}
export SUB_PATH=${SUB_PATH:-${URL}}
export CLASH_PATH=${CLASH_PATH:-${CLASH_URL}}
export LOCAL_MODE=${LOCAL_MODE:-on}
export SUB_NAME=${SUB_NAME:-Aggregated}
export CONFIG_DIR=${CONFIG_DIR:-/app/configs}
export LOG_LEVEL=${LOG_LEVEL:-info}

mkdir -p "$CONFIG_DIR"

echo "Starting FastAPI on port $PORT"
echo "Configuration:"
if [ -n "$SUB_PATH" ]; then
	echo "  SUB_PATH: $SUB_PATH"
else
	echo "  SUB_PATH: <disabled>"
fi
if [ -n "$CLASH_PATH" ]; then
	echo "  CLASH_PATH: $CLASH_PATH"
else
	echo "  CLASH_PATH: <disabled>"
fi
echo "  LOCAL_MODE: $LOCAL_MODE"
echo "  SUB_NAME: $SUB_NAME"
echo "  CONFIG_DIR: $CONFIG_DIR"
echo "  LOG_LEVEL: $LOG_LEVEL"

# Run FastAPI
exec uvicorn main:app --app-dir /app --host 0.0.0.0 --port $PORT --log-level "$LOG_LEVEL"
