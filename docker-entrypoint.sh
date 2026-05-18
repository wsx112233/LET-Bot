#!/bin/sh
set -eu

mkdir -p /app/data
chown -R appuser:appuser /app/data 2>/dev/null || true

exec runuser -u appuser -- "$@"
