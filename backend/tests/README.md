# Test Suite for Timelapser Backend

This directory contains comprehensive tests for the Timelapser v4 backend.

## Getting Started

### Install Test Dependencies

```bash
# Install pytest and related packages
python run_tests.py install

# Or install manually
pip install pytest pytest-asyncio pytest-cov
```

### Running Tests

```bash
# Run cache-related tests (good starting point)
python run_tests.py cache

# Run all tests
python run_tests.py all

# Run with coverage report
python run_tests.py coverage
```

### Direct pytest commands

```bash
# Run specific test file
pytest tests/test_cache_manager.py -v

# Run specific test class
pytest tests/test_cache_manager.py::TestMemoryCache -v

# Run specific test method
pytest tests/test_cache_manager.py::TestMemoryCache::test_basic_set_and_get -v

# Run with pattern matching
pytest -k "test_cache" -v
```

## Test Structure

### Core Test Files

- `test_cache_manager.py` - Tests for the core caching infrastructure

  - MemoryCache class functionality
  - TTL expiration behavior
  - ETag generation and validation utilities
  - Caching decorators
  - Global cache operations

- `test_cache_invalidation.py` - Tests for cache invalidation service

  - SSE event-driven invalidation
  - ETag-aware smart invalidation
  - Utility methods for cache management
  - Error handling

- `conftest.py` - Shared pytest fixtures and configuration
  - Cache instances for testing
  - Mock services and data generators
  - Helper functions for testing scenarios

### Test Categories

Tests are organized by functionality and marked with categories:

- **Unit Tests**: Test individual functions and methods in isolation
- **Integration Tests**: Test interaction between components
- **Cache Tests**: Specifically test caching functionality (good starting point)

## Test Fixtures

The test suite provides several fixtures for common testing scenarios:

### Cache Fixtures

- `fresh_cache` - Clean MemoryCache instance for each test
- `populated_cache` - Pre-populated cache with test data
- `cache_invalidation_service` - Service instance for invalidation testing

### Mock Services

- `mock_settings_service` - Mock settings service for dependency injection
- `sample_cache_data` - Sample data for testing cache scenarios
- `etag_test_objects` - Objects with timestamps for ETag testing

### Helper Functions

- `verify_cache_hit(cache, key, expected_value)` - Verify cache contains
  expected data
- `verify_cache_miss(cache, key)` - Verify cache does not contain key
- `verify_cache_expiration(cache, key, ttl_seconds)` - Test TTL behavior
- `generate_test_data(count, prefix)` - Generate test data sets

## Best Practices

### Writing Tests

1. **Use descriptive test names** that explain what is being tested
2. **Follow the AAA pattern**: Arrange, Act, Assert
3. **Test both success and failure scenarios**
4. **Use appropriate fixtures** to avoid test data setup duplication
5. **Mock external dependencies** (databases, APIs, file systems)

### Cache Testing Patterns

```python
@pytest.mark.asyncio
async def test_cache_operation(fresh_cache):
    # Arrange
    key = "test_key"
    value = "test_value"

    # Act
    await fresh_cache.set(key, value)
    result = await fresh_cache.get(key)

    # Assert
    assert result == value
```

### ETag Testing Patterns

```python
def test_etag_generation(etag_test_objects):
    # Use pre-generated test objects with timestamps
    camera = etag_test_objects["camera"]
    etag = generate_timestamp_etag(camera)

    expected_timestamp = camera["updated_at"].timestamp()
    expected_etag = f'"{expected_timestamp}"'

    assert etag == expected_etag
```

## Coverage Goals

The test suite aims for high coverage of critical components:

- **Cache Manager**: >90% coverage of core caching functionality
- **Cache Invalidation**: >85% coverage of invalidation logic
- **ETag Utilities**: >95% coverage of ETag generation and validation
- **Error Handling**: All error paths should be tested

## Continuous Integration

These tests are designed to be run in CI/CD pipelines:

```bash
# CI-friendly command with JUnit XML output
pytest tests/ --junitxml=test-results.xml --cov=app --cov-report=xml
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the backend directory is in PYTHONPATH
2. **Async Test Failures**: Verify `pytest-asyncio` is installed
3. **Cache State Issues**: Use `fresh_cache` fixture for clean state
4. **Mock Issues**: Check that patches target the correct module path

### Debug Mode

Run tests with additional debugging:

```bash
pytest tests/ -v -s --tb=long --log-cli-level=DEBUG
```

This will show all print statements and detailed error traces.
