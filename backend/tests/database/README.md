# Database Operations Tests

Simple, focused tests for our database operations layer, covering the key optimizations we implemented.

## Test Structure

```
tests/database/
├── __init__.py
├── conftest.py                    # Shared fixtures and test utilities
├── test_corruption_operations.py  # Tests for corruption database operations
└── README.md                      # This file
```

## Running Tests

### Run all database tests:
```bash
cd backend
python -m pytest tests/database/ -v
```

### Run specific test file:
```bash
python -m pytest tests/database/test_corruption_operations.py -v
```

### Run tests with coverage:
```bash
python -m pytest tests/database/ --cov=app.database --cov-report=html
```

### Run only unit tests (skip integration):
```bash
python -m pytest tests/database/ -v -m "not integration"
```

### Run only caching tests:
```bash
python -m pytest tests/database/ -v -m "caching"
```

## Test Categories

### **Unit Tests**
- **Query Builders**: Test SQL generation without database
- **Caching Decorators**: Verify `@cached_response` is applied  
- **ETag Generation**: Test collection ETag behavior
- **Method Logic**: Test business logic with mocked database

### **Integration Tests** (marked with `@pytest.mark.integration`)
- **Full Database Workflow**: End-to-end operations with test database
- **Cache Performance**: Verify caching actually improves speed
- **Real Query Execution**: Test against actual database

## What We're Testing

Our tests focus on validating the database optimizations we implemented:

✅ **Caching System**
- `@cached_response` decorators are applied correctly
- Cache invalidation patterns work
- TTL values are appropriate

✅ **Time Management** 
- `utc_now()` is used instead of `NOW()` in SQL
- Parameters are passed correctly to queries
- No direct SQL timestamp generation

✅ **Query Builders**
- SQL generation produces valid queries
- Parameterization prevents SQL injection
- Query optimization patterns are followed

✅ **ETag Support**
- Collection methods can generate ETags
- ETag functions are imported where needed
- Cache validation works with ETags

✅ **Error Handling**
- Database connection failures are handled
- Invalid data doesn't crash operations
- Rollback scenarios work correctly

## Adding New Tests

When adding tests for new database operations files:

1. **Create test file**: `test_[operation_name]_operations.py`
2. **Use shared fixtures**: Import from `conftest.py`
3. **Follow naming**: `test_[method_name]_[aspect]`
4. **Test key areas**: Caching, query building, error handling
5. **Keep it simple**: Focus on critical functionality

## Test Data

Use the `TestDataFactory` from `conftest.py` for consistent test data:

```python
def test_something(test_data):
    camera_data = test_data.create_camera_data(name="Special Camera")
    corruption_data = test_data.create_corruption_log_data(camera_id=camera_data["id"])
```

## Future Enhancements

- **Performance benchmarks**: Time query execution
- **Load testing**: Test with large datasets  
- **Integration with test database**: Full end-to-end testing
- **Property-based testing**: Generate random valid inputs
- **Mutation testing**: Verify test quality

These tests provide a solid foundation that we can expand as needed!