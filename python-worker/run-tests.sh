#!/bin/bash

# Test runner script for the timelapser Python worker

set -e

echo "🧪 Timelapser Python Worker Test Suite"
echo "======================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup-worker.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Install/update test dependencies
echo "📦 Installing/updating test dependencies..."
pip install -q -r requirements.txt

# Run tests with different verbosity levels based on argument
case "${1:-standard}" in
    "quick")
        echo "🏃 Running quick tests (unit tests only)..."
        python -m pytest tests/ -v -m "not slow" --tb=short
        ;;
    "coverage")
        echo "📊 Running tests with coverage report..."
        python -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov
        echo "📄 Coverage report saved to htmlcov/index.html"
        ;;
    "verbose")
        echo "🔍 Running tests with verbose output..."
        python -m pytest tests/ -vv --tb=long
        ;;
    "standard"|*)
        echo "🧪 Running standard test suite..."
        python -m pytest tests/ -v
        ;;
esac

echo ""
echo "✅ Test run complete!"
echo ""
echo "Available test options:"
echo "  ./run-tests.sh quick      - Run only fast unit tests"
echo "  ./run-tests.sh coverage   - Run tests with coverage report"
echo "  ./run-tests.sh verbose    - Run tests with detailed output"
echo "  ./run-tests.sh standard   - Run all tests (default)"
