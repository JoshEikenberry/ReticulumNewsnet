#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
npm ci
npm run build
echo "[newsnet-frontend] Build complete: dist/"
