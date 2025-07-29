#!/bin/bash

# Script to clean all __pycache__ directories from the timelapser-v4 codebase
# This script will find and remove all __pycache__ directories while excluding venv

echo "🧹 Cleaning __pycache__ directories from timelapser-v4 codebase..."

# Get the script directory (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧹 Cleaning .pytest_cache directories..."
pytest_cache_count=0

# Find and remove .pytest_cache directories, excluding venv directories
while IFS= read -r -d '' pytest_cache_dir; do
  if [[ "$pytest_cache_dir" == *"/venv/"* ]]; then
    echo "⏭️  Skipping (in venv): $pytest_cache_dir"
    continue
  fi
  echo "🗑️  Removing: $pytest_cache_dir"
  rm -rf "$pytest_cache_dir"
  ((pytest_cache_count++))
done < <(find "$SCRIPT_DIR" -type d -name ".pytest_cache" -print0)

# Counter for removed directories
removed_count=0

# Find and remove __pycache__ directories, excluding venv directories
while IFS= read -r -d '' pycache_dir; do
  # Check if the path contains 'venv' - if so, skip it
  if [[ "$pycache_dir" == *"/venv/"* ]]; then
    echo "⏭️  Skipping (in venv): $pycache_dir"
    continue
  fi

  echo "🗑️  Removing: $pycache_dir"
  rm -rf "$pycache_dir"
  ((removed_count++))
done < <(find "$SCRIPT_DIR" -type d -name "__pycache__" -print0)

# Also clean .pyc files that might be outside __pycache__ directories
echo ""
echo "🧹 Cleaning standalone .pyc files..."
pyc_count=0

while IFS= read -r -d '' pyc_file; do
  # Check if the path contains 'venv' - if so, skip it
  if [[ "$pyc_file" == *"/venv/"* ]]; then
    continue
  fi

  echo "🗑️  Removing: $pyc_file"
  rm -f "$pyc_file"
  ((pyc_count++))
done < <(find "$SCRIPT_DIR" -type f -name "*.pyc" -print0)

# Clean .pyo files as well (Python optimization files)
echo ""
echo "🧹 Cleaning .pyo files..."
pyo_count=0

while IFS= read -r -d '' pyo_file; do
  # Check if the path contains 'venv' - if so, skip it
  if [[ "$pyo_file" == *"/venv/"* ]]; then
    continue
  fi

  echo "🗑️  Removing: $pyo_file"
  rm -f "$pyo_file"
  ((pyo_count++))
done < <(find "$SCRIPT_DIR" -type f -name "*.pyo" -print0)

echo ""
echo "✅ Cleanup complete!"
echo "📊 Summary:"
echo "   - __pycache__ directories removed: $removed_count"
echo "   - .pytest_cache directories removed: $pytest_cache_count"
echo "   - .pyc files removed: $pyc_count"
echo "   - .pyo files removed: $pyo_count"
echo "   - Virtual environment directories were preserved"
echo ""
