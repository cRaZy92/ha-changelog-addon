#!/usr/bin/with-contenv bash
set -e

echo "Starting Changelog Generator addon..."

export HOME=/root
git config --global --add safe.directory /config

cd /app
exec python3 -m app.server
