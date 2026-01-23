#!/usr/bin/env bash
# Setup script for pre-commit hooks
# Run this script once after cloning the repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Setting up pre-commit hooks for news-scraper..."

# Check if we're in a git repository
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "Error: Not a git repository. Please run this from the project root."
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "pre-commit not found. Installing..."

    # Try pip first
    if command -v pip &> /dev/null; then
        pip install pre-commit
    elif command -v pip3 &> /dev/null; then
        pip3 install pre-commit
    else
        echo "Error: pip not found. Please install pre-commit manually:"
        echo "  pip install pre-commit"
        exit 1
    fi
fi

echo "Installing pre-commit hooks..."
pre-commit install

echo "Installing commit-msg hook for conventional commits (optional)..."
pre-commit install --hook-type commit-msg || true

echo ""
echo "Pre-commit hooks installed successfully!"
echo ""
echo "Usage:"
echo "  - Hooks will run automatically on 'git commit'"
echo "  - Run manually on all files: pre-commit run --all-files"
echo "  - Run a specific hook: pre-commit run <hook-id>"
echo "  - Skip hooks temporarily: git commit --no-verify"
echo ""
echo "To update hooks to latest versions:"
echo "  pre-commit autoupdate"
