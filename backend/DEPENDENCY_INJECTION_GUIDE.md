# Dependency Injection Developer Guide
## Timelapser v4 Backend Architecture

### Overview

The Timelapser v4 backend uses dependency injection to optimize database connections and create a maintainable, testable architecture. This system eliminates database connection pool exhaustion while providing clear patterns for service composition.

**Core Principle**: Share database connections through singleton Operations instances where beneficial, with context-appropriate fallback patterns.

---

## Architecture Components

### 1. Singleton Registry (`app/dependencies/registry.py`)
- Thread-safe service registry with factory pattern
- Manages lifecycle of shared Operations instances
- Provides foundation for dependency injection system

### 2. Operations Factories (`app/dependencies/specialized.py`)
- 30 factory functions for Operations classes
- Both async and sync variants available
- Registered as singletons for optimal connection sharing

### 3. Service Factories (`app/dependencies/{async,sync}_services.py`)
- High-level service dependency injection
- Proper Operations injection into services
- Prevents circular import issues

### 4. Type Annotations (`app/dependencies/type_annotations.py`)
- FastAPI dependency injection types
- Clean router signatures with IDE support
- Example: `CameraOperationsDep`, `ImageOperationsDep`

---

## Core Patterns

### Pattern 1: Router Endpoints (FastAPI Dependencies)
**Use Case**: All HTTP endpoints
**Pattern**: Always use FastAPI dependency injection

```python
from ..dependencies.type_annotations import CameraOperationsDep

async def get_camera(
    camera_id: int,
    camera_ops: CameraOperationsDep = Depends(),  # Auto-injected singleton
):
    return await camera_ops.get_camera(camera_id)
```

**Critical**: Always include `= Depends()` for parameters without defaults to avoid syntax errors.

### Pattern 2: Async Services (Direct Instantiation)
**Use Case**: Services that run in async contexts
**Pattern**: Use direct instantiation in fallback methods

```python
class CameraService:
    def __init__(self, db, camera_ops=None):
        self.db = db
        self.camera_ops = camera_ops or self._get_default_camera_ops()
    
    def _get_default_camera_ops(self):
        """Simple, reliable fallback for async services"""
        from ...database.camera_operations import CameraOperations
        return CameraOperations(self.db)
```

**Why**: Avoids complex `asyncio.run()` patterns and event loop issues.

### Pattern 3: Sync Services (Singleton First)
**Use Case**: Worker processes and sync contexts
**Pattern**: Use singleton factories where available

```python
class CameraWorker:
    def __init__(self, db, camera_ops=None):
        self.db = db
        self.camera_ops = camera_ops or self._get_default_camera_ops()
    
    def _get_default_camera_ops(self):
        """Use singleton for optimal connection sharing"""
        from ..dependencies.specialized import get_sync_camera_operations
        return get_sync_camera_operations()
```

**Why**: Maximizes connection sharing in sync contexts where singletons work reliably.

---

## Available Dependencies

### Operations Singletons
```python
# Async versions
from ..dependencies.specialized import (
    get_camera_operations,
    get_image_operations,
    get_video_operations,
    get_timelapse_operations,
    get_settings_operations,
    get_corruption_operations,
    get_sse_events_operations,
    # ... all Operations classes have async factories
)

# Sync versions  
from ..dependencies.specialized import (
    get_sync_camera_operations,
    get_sync_image_operations,
    get_sync_video_operations,
    # ... all Operations classes have sync factories
)
```

### FastAPI Dependency Types
```python
from ..dependencies.type_annotations import (
    CameraOperationsDep,
    ImageOperationsDep, 
    VideoOperationsDep,
    SettingsOperationsDep,
    # ... all Operations have corresponding Dep types
)
```

### Service Dependencies
```python
# Async services
from ..dependencies.async_services import (
    get_camera_service,
    get_image_service,
    get_video_service,
)

# Sync services
from ..dependencies.sync_services import (
    get_sync_camera_service,
    get_sync_image_service,
)
```

---

## Decision Matrix: When to Use What

| Context | Pattern | Reasoning |
|---------|---------|-----------|
| **HTTP Endpoints** | FastAPI DI (`SomeOperationsDep`) | Clean, automatic, no manual instantiation |
| **Async Services** | Direct instantiation | Avoids asyncio complexity, simple and reliable |
| **Sync Workers** | Singleton factories | Optimal connection sharing in sync contexts |
| **Pipeline Services** | Constructor injection + context-appropriate fallbacks | Flexible, testable, follows service patterns |

---

## Common Patterns by Use Case

### ✅ Router Pattern (100% Success Rate)
```python
async def endpoint(
    data: RequestModel,
    ops: OperationsDep = Depends(),
):
    return await ops.do_something()
```

### ✅ Async Service Pattern (Simplest and Most Reliable)  
```python
def _get_default_ops(self):
    from ...database.operations import Operations
    return Operations(self.db)
```

### ✅ Sync Service Pattern (Leverage Singletons)
```python
def _get_default_ops(self):
    from ..dependencies.specialized import get_sync_operations
    return get_sync_operations()
```

### ❌ Anti-Patterns (Avoid These)
```python
# DON'T: Direct instantiation in routers
camera_ops = CameraOperations(db)

# DON'T: Complex asyncio patterns in services
async def _get_default_ops(self):
    return await get_operations()  # Sync constructor calling async

# DON'T: Missing Depends() in FastAPI
async def endpoint(ops: OperationsDep):  # Syntax error if other params have defaults
```

---

## Adding New Components

### New Operations Class
1. **Create the Operations class** with both sync and async variants
2. **Add factory functions** in `specialized.py`:
```python
def _create_foo_operations():
    return FooOperations(async_db)

def _create_sync_foo_operations():
    return SyncFooOperations(sync_db)

register_singleton_factory("foo_operations", _create_foo_operations)
register_singleton_factory("sync_foo_operations", _create_sync_foo_operations)

async def get_foo_operations() -> "FooOperations":
    return await get_async_singleton_service("foo_operations")

def get_sync_foo_operations() -> "SyncFooOperations":
    return get_singleton_service("sync_foo_operations")
```

3. **Add type annotation** in `type_annotations.py`:
```python
FooOperationsDep = Annotated[FooOperations, Depends(get_foo_operations)]
```

### New Service Class
1. **Use constructor injection**:
```python
class FooService:
    def __init__(self, db, foo_ops=None):
        self.foo_ops = foo_ops or self._get_default_foo_ops()
    
    def _get_default_foo_ops(self):
        # For async services
        from ...database.foo_operations import FooOperations
        return FooOperations(self.db)
        
        # For sync services  
        # from ..dependencies.specialized import get_sync_foo_operations
        # return get_sync_foo_operations()
```

---

## Troubleshooting Guide

### Common Issues and Solutions

**Import Errors**
- ❌ Problem: `ImportError` or circular imports
- ✅ Solution: Use direct imports in fallback methods: `from ...database.operations import Operations`

**FastAPI Parameter Errors**  
- ❌ Problem: `SyntaxError` about parameters without defaults
- ✅ Solution: Always include `= Depends()` for dependency injection parameters

**Event Loop Issues**
- ❌ Problem: `RuntimeError` about event loops in service constructors
- ✅ Solution: Use direct instantiation for async services instead of `asyncio.run()`

**Connection Pool Issues**
- ❌ Problem: Still seeing connection multiplication
- ✅ Solution: Check for direct Operations instantiation; use patterns above

### Validation Checklist
Before committing code with dependency injection changes:

- [ ] **Compilation test**: `python -m py_compile modified_file.py`
- [ ] **Import test**: Verify all import paths work
- [ ] **Pattern check**: Async services use direct instantiation, sync services use singletons
- [ ] **FastAPI syntax**: All dependency parameters include `= Depends()`
- [ ] **No direct instantiation**: Routers use dependency injection only

---

## Architecture Benefits

### Performance
- **Eliminated connection pool exhaustion** through strategic singleton usage
- **Reduced memory footprint** via shared instances where beneficial
- **Faster initialization** through pattern simplicity

### Maintainability  
- **Clear patterns** for different contexts (async vs sync)
- **Consistent architecture** across the entire codebase
- **Simple debugging** with straightforward fallback methods

### Testability
- **Easy mocking** through constructor injection
- **Isolated testing** with clear dependency boundaries
- **Flexible test setup** using either mocks or real instances

---

## Best Practices Summary

1. **Routers**: Always use FastAPI dependency injection with `= Depends()`
2. **Async Services**: Use direct instantiation in fallbacks for simplicity
3. **Sync Services**: Use singleton factories for optimal connection sharing
4. **Testing**: Mock through constructor injection, validate compilation
5. **New Components**: Follow the established patterns, test import paths

**Remember**: The goal is reliable, maintainable code that eliminates connection pool issues while providing clear patterns for developers to follow.