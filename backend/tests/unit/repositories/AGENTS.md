# Unit Tests - Repositories

## Purpose

The `backend/tests/unit/repositories/` directory contains unit tests for repository classes. Unlike integration tests that use real databases, these tests mock the database session to verify repository logic in isolation.

## Directory Structure

```
backend/tests/unit/repositories/
├── AGENTS.md                            # This file
├── __init__.py                          # Package initialization
├── test_base_repository.py              # Base repository tests (8KB)
├── test_entity_repository_additions.py  # Entity repository extension tests (13KB)
└── test_entity_repository.py            # Entity repository tests (40KB)
```

## Test Files (3 total)

| File                                  | Repository Tested | Key Coverage                    |
| ------------------------------------- | ----------------- | ------------------------------- |
| `test_base_repository.py`             | BaseRepository    | Generic CRUD, error handling    |
| `test_entity_repository.py`           | EntityRepository  | Entity management, trust levels |
| `test_entity_repository_additions.py` | EntityRepository  | Extended entity features        |

## Running Tests

```bash
# All repository unit tests
uv run pytest backend/tests/unit/repositories/ -v

# Specific repository tests
uv run pytest backend/tests/unit/repositories/test_entity_repository.py -v

# With coverage
uv run pytest backend/tests/unit/repositories/ -v --cov=backend.repositories
```

## Test Categories

### Base Repository Tests (`test_base_repository.py`)

Tests for generic repository functionality:

| Test Class                     | Coverage                      |
| ------------------------------ | ----------------------------- |
| `TestBaseRepositoryCRUD`       | Create, read, update, delete  |
| `TestBaseRepositoryErrors`     | Error handling and edge cases |
| `TestBaseRepositoryPagination` | Limit and offset pagination   |

### Entity Repository Tests (`test_entity_repository.py`)

Tests for entity management:

| Test Class                      | Coverage                       |
| ------------------------------- | ------------------------------ |
| `TestEntityCreation`            | Entity creation and validation |
| `TestEntityRetrieval`           | Find by ID, name, attributes   |
| `TestEntityTrustClassification` | Trust level assignment         |
| `TestEntityAppearances`         | Appearance tracking            |
| `TestEntityAssociations`        | Event associations             |

### Entity Repository Extensions (`test_entity_repository_additions.py`)

Tests for additional entity features:

| Test Class             | Coverage                   |
| ---------------------- | -------------------------- |
| `TestEntitySearch`     | Full-text entity search    |
| `TestEntityMerge`      | Duplicate entity merging   |
| `TestEntityStatistics` | Entity activity statistics |

## Test Patterns

### Mocked Session Pattern

```python
@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.mark.asyncio
async def test_create_entity(mock_session):
    repository = EntityRepository(mock_session)

    entity = await repository.create(
        name="John Doe",
        entity_type="person",
        trust_level="known"
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
```

### Error Handling Pattern

```python
@pytest.mark.asyncio
async def test_handles_not_found(mock_session):
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    repository = EntityRepository(mock_session)

    result = await repository.get_by_id("nonexistent")

    assert result is None
```

## Mocking Guidelines

1. **Mock at session level** - Mock `execute`, `add`, `commit`, `refresh`
2. **Use `AsyncMock`** for async methods
3. **Configure return values** to simulate database responses
4. **Verify method calls** to ensure correct SQL operations

## Related Documentation

- `/backend/repositories/AGENTS.md` - Repository implementations
- `/backend/tests/integration/repositories/AGENTS.md` - Repository integration tests
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
