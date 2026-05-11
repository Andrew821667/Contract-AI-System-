#!/usr/bin/env bash
set -euo pipefail

REDIS_HOME="/Users/legalai/.local/redis"
REDIS_CONF="/Users/legalai/.config/contract-ai/redis.conf"
APP_HOME="/Users/legalai/projects/Contract-AI-System-"
REDIS_CLI="$REDIS_HOME/bin/redis-cli"
REDIS_SERVER="$REDIS_HOME/bin/redis-server"

if [[ ! -x "$REDIS_SERVER" || ! -x "$REDIS_CLI" || ! -f "$REDIS_CONF" ]]; then
  exit 0
fi

if "$REDIS_CLI" -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
  exit 0
fi

mkdir -p "$APP_HOME/logs"
nohup "$REDIS_SERVER" "$REDIS_CONF" \
  > "$APP_HOME/logs/redis.out.log" \
  2> "$APP_HOME/logs/redis.err.log" &
echo $! > "$APP_HOME/.redis.pid"
