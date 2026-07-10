#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/studybuddy_server.pid"
LOG_FILE="$DIR/server.log"
PORT="${STUDYBUDDY_PORT:-6003}"

cd "$DIR"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    open "http://127.0.0.1:${PORT}/login"
    echo "StudyBuddy is already running on port ${PORT}."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use. Stop the existing process first."
  exit 1
fi

PORT="$PORT" ./StudyBuddyServer >"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 2

if ! kill -0 "$PID" 2>/dev/null; then
  echo "StudyBuddy failed to start. Check server.log"
  exit 1
fi

open "http://127.0.0.1:${PORT}/login"
echo "StudyBuddy started: http://127.0.0.1:${PORT}/login"
