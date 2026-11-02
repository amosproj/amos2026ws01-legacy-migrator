#!/usr/bin/env bash
set -euo pipefail

# Require source and output directories
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <source-dir> <output-dir>"
    exit 1
fi

# Find the repository root, independently of the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && pwd)"

# Resolve the source directory to an absolute path
if [ ! -d "$1" ]; then
    echo "Error: Source directory does not exist: $1"
    exit 1
fi
SOURCE_DIR="$(cd "$1" && pwd -P)"

# Create the output directory if necessary and resolve its path
mkdir -p "$2"
OUTPUT_DIR="$(cd "$2" && pwd -P)"

# Run Graphify through Docker Compose
sudo env \
    SOURCE_DIR="$SOURCE_DIR" \
    OUTPUT_DIR="$OUTPUT_DIR" \
    docker compose -f "$PROJECT_ROOT/compose.yaml" run --rm graphify
