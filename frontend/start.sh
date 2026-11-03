#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== SunsetTracker Frontend Setup & Start ==="

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting Vite development server on http://localhost:3000..."
npm run dev -- --host
