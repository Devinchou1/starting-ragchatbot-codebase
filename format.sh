#!/bin/bash

# Code Formatting Script
# Automatically formats and fixes code quality issues

set -e  # Exit on error

echo "🎨 Formatting code..."
echo ""

# Format with black
echo "📝 Running black formatter..."
uv run black backend/
echo "✅ Black formatting complete"
echo ""

# Fix linting issues with ruff
echo "🔧 Auto-fixing linting issues with ruff..."
uv run ruff check --fix backend/
echo "✅ Ruff auto-fix complete"
echo ""

echo "✨ Code formatting complete!"
