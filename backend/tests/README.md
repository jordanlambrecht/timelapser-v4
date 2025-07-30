# Test Suite for Timelapser Backend

This directory contains comprehensive tests for the Timelapser v4 backend.

## Getting Started

### Install Test Dependencies

```bash
# Activate virtual environment first
source backend/venv/bin/activate

# Install test dependencies using pip
pip install pytest pytest-asyncio pytest-cov
```

### Running Tests

```bash
# Run database operation tests (our latest optimized tests)
pytest tests/database/ -v

# Run all unit tests
pytest tests/unit/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html
```

## Test Structure

### Directory Organization

```
tests/
├── database/              # Database operation tests (latest, most comprehensive)
│   ├── test_corruption_query_builder.py
│   ├── test_camera_operations.py
│   ├── test_image_operations.py
│   └── conftest.py        # Database test fixtures
├── unit/                  # Unit tests organized by component type
│   ├── database/          # Database operation unit tests
│   ├── services/          # Service layer unit tests
│   └── utils/             # Utility function unit tests
├── integration/           # Integration tests
├── frontend_integration/  # Frontend integration tests
├── fixtures/              # Shared test fixtures and data
└── conftest.py           # Global test configuration
```

### Core Test Categories

#### Database Tests (`tests/database/`)
**Latest and most comprehensive** - These tests use sophisticated patterns:
- **Caching behavior**: Tests for @cached_response decorators
- **ETag generation**: Collection and timestamp ETags
- **Query optimization**: Parameterized queries, no NOW() calls
- **SQL patterns**: Query builders, efficient JOINs, batch operations

#### Unit Tests (`tests/unit/`)
Organized by component type:
- **database/**: Database operation unit tests
- **services/**: Service layer tests (workers, weather, overlays)
- **utils/**: Utility function tests (caching, thumbnails, generators)

#### Integration Tests (`tests/integration/`)
- End-to-end workflow tests
- Component interaction tests

## Key Test Files

### Database Operations (Recommended Starting Point)
- `tests/database/test_corruption_query_builder.py` - SQL generation tests (14 tests)
- `tests/database/test_camera_operations.py` - Camera operations tests (13 tests)  
- `tests/database/test_image_operations.py` - Image operations tests (19 tests)

### Unit Tests by Category
- `tests/unit/database/` - Database operation unit tests
- `tests/unit/services/` - Service layer unit tests
- `tests/unit/utils/` - Utility and helper function tests

## Test Fixtures

### Database Test Fixtures (`tests/database/conftest.py`)
- `mock_async_db` - Mock async database connections
- `mock_sync_db` - Mock sync database connections  
- `test_data` - Test data factory for consistent mock data
- `mock_current_time` - Consistent timestamps for testing

### Helper Functions
- `assert_sql_contains_patterns()` - Verify SQL contains required patterns
- `assert_sql_not_contains()` - Verify SQL avoids forbidden patterns
- `create_test_*_data()` - Data factories for different model types

## Testing Patterns

### Database Operation Testing
```python
def test_query_pattern(self):
    \"\"\"Test that queries follow optimization patterns.\"\"\"
    query = build_some_query()
    
    # Should use parameterization
    assert \"%s\" in query
    # Should avoid NOW() calls
    assert \"NOW()\" not in query
    # Should use proper JOINs
    assert \"LEFT JOIN\" in query
```

### Caching Pattern Testing
```python
@pytest.mark.caching
def test_collection_etag_generation(self):
    \"\"\"Test collection ETag generation.\"\"\"
    items = [MockItem(id=1), MockItem(id=2)]
    etag = generate_collection_etag(items)
    assert etag.startswith('\"2-')  # Count + timestamp
```

### Mock Database Testing
```python
def test_async_operation(mock_async_db):
    db, conn, cursor = mock_async_db
    # Test async database operations with proper mocking
```

## Running Specific Test Categories

```bash
# Run the latest comprehensive database tests
pytest tests/database/ -v

# Run caching-specific tests
pytest -m caching -v

# Run integration tests only
pytest -m integration -v

# Run query builder tests
pytest -m query_builder -v

# Run specific test file
pytest tests/database/test_camera_operations.py -v

# Run specific test method
pytest tests/database/test_camera_operations.py::TestCameraQueryPatterns::test_active_cameras_query_pattern -v
```

## Best Practices

### Database Testing
1. **Use query builders** for centralized SQL construction
2. **Test SQL patterns** rather than actual database calls
3. **Mock database connections** to avoid external dependencies
4. **Verify parameterization** to prevent SQL injection
5. **Test caching decorators** and ETag generation

### General Testing
1. **Use descriptive test names** that explain the behavior being tested
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Test both success and failure scenarios**
4. **Use appropriate fixtures** for consistent test data
5. **Mock external dependencies** (databases, APIs, file systems)

## Coverage Goals

- **Database Operations**: >90% coverage of query patterns and caching
- **Service Layer**: >85% coverage of business logic
- **Utility Functions**: >95% coverage of helper functions
- **Error Handling**: All error paths should be tested

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure you're in the backend directory and virtual environment is activated
2. **Async Test Failures**: Verify `pytest-asyncio` is installed
3. **Mock Issues**: Check that patches target the correct module path
4. **Circular Import Issues**: Tests avoid importing from app.database to prevent circular imports

### Debug Mode
```bash
pytest tests/ -v -s --tb=long --log-cli-level=DEBUG
```

### Running with Coverage
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
```