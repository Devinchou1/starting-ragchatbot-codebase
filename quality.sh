#!/bin/bash

# Code Quality Check Script
# Runs formatting, linting, and type checking

set -e  # Exit on error

echo "🔍 Running code quality checks..."
echo ""

# Format check with black
echo "📝 Checking code formatting with black..."
uv run black --check backend/
echo "✅ Black formatting check passed"
echo ""

# Lint with ruff
echo "🔎 Linting with ruff..."
uv run ruff check backend/
echo "✅ Ruff linting passed"
echo ""

# Type check with mypy
echo "🔬 Type checking with mypy..."
uv run mypy backend/ --exclude backend/tests/
echo "✅ Mypy type checking passed"
echo ""

echo "✨ All quality checks passed!"
