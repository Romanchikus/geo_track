#!/bin/sh
set -e

if ! cmp -s package-lock.json node_modules/.package-lock.json 2>/dev/null; then
  npm ci
  cp package-lock.json node_modules/.package-lock.json
fi

exec "$@"
