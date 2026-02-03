# 0. Standards of Development

This document establishes the development methodology, quality standards, and tooling requirements for this project.

---

## 0.1 Development Methodology

This project follows the **Ralph Wiggum** autonomous development methodology.

### Core Principles

1. **State in Files** - Progress persists in files and git, not conversation context
2. **Iterative Completion** - One criterion at a time, committed incrementally
3. **Fail Forward** - Learn from failures via guardrails, don't repeat mistakes
4. **Fresh Context** - Each session reads state from files, enabling seamless continuation

### Task Management

All development work is tracked in `RALPH_TASK.md`:

```yaml
---
task: Description of what to build
test_command: "pytest tests/ -v"
browser_validation: true
base_url: "http://localhost:8000"
---

## Success Criteria

1. [ ] First criterion - specific, testable
2. [ ] Second criterion - atomic, achievable
```

### State Files

The `.ralph/` directory contains:

| File | Purpose |
|------|---------|
| `progress.md` | Session history and accomplishments |
| `guardrails.md` | Lessons learned from failures |
| `screenshots/` | Browser validation evidence |

---

## 0.2 Quality Standards

### Code Quality

| Standard | Requirement |
|----------|-------------|
| **Type Safety** | All code must pass type checking |
| **Linting** | No linting errors in committed code |
| **Formatting** | Consistent formatting (auto-format on save) |
| **Documentation** | Public APIs must have docstrings |

#### Python Reference (adapt for other languages)

- Follow PEP 8
- Use type hints for all function parameters and returns
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes
- Tools: `black` for formatting, `ruff` for linting

```python
from typing import Optional

async def lookup_item(
    item_id: str,
    include_metadata: bool = True,
) -> Optional[ItemDetail]:
    """
    Look up item information by ID.
    
    Args:
        item_id: The item identifier
        include_metadata: Whether to include additional metadata
    
    Returns:
        Item details if found, None otherwise
    
    Raises:
        LookupError: If the lookup service fails
    """
    pass
```

### Testing Requirements

| Level | Coverage Target | When Required |
|-------|-----------------|---------------|
| Unit Tests | >80% | All business logic |
| Integration Tests | Critical paths | API endpoints, database operations |
| Database Tests | Migrations | Schema changes |
| Browser Tests | UI criteria | Forms, navigation, user flows |

#### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
├── integration/             # Integration tests
└── database/                # Migration and CRUD tests
```

#### Fixture Patterns

- Use **session-scoped** fixtures for database engines
- Use **function-scoped** fixtures for database sessions (with rollback)
- Mock external services in tests

### Commit Standards

#### During Ralph Sessions

- **Format**: `ralph: [N] Description` where N is criterion number
- **Frequency**: One commit per completed criterion
- **Content**: Each commit should be atomic and reversible

#### General Development (Conventional Commits)

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

**Examples:**
```
feat(api): add product lookup endpoint
fix(scanner): handle empty barcode input
docs(readme): add installation instructions
```

---

## 0.3 MCP Tool Integration

### Browser Validation

For UI-related criteria, MCP browser tools provide validation:

```
Workflow:
1. browser_navigate → Open target page
2. browser_lock → Lock for interactions
3. browser_snapshot → Inspect before interacting
4. [interactions] → click, type, fill
5. browser_screenshot → Capture evidence
6. browser_unlock → Release browser
```

### Evidence Collection

- Screenshots saved to `.ralph/screenshots/`
- Named: `criterion-N-description.png`
- Referenced in `progress.md`

---

## 0.4 Git Workflow

### Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code |
| `ralph/*` | Ralph Wiggum development branches |
| `feature/*` | Manual feature development |

### Commit Protocol

1. Commit after each completed criterion
2. Use `ralph: ` prefix for all Ralph commits
3. Push after every 3-5 commits
4. Never force push to shared branches

---

## 0.5 Definition of Done

A criterion is complete when:

- [ ] Code implemented and compiles
- [ ] All tests pass (`test_command` succeeds)
- [ ] Browser validation passes (if UI criterion)
- [ ] Changes committed with `ralph: [N]` prefix
- [ ] `RALPH_TASK.md` updated: `[ ]` → `[x]`
- [ ] `.ralph/progress.md` updated with summary

---

## 0.6 Failure Handling

When something fails:

1. **Don't Repeat** - Same approach failing twice = add guardrail
2. **Document** - Add to `.ralph/guardrails.md`:
   ```markdown
   ### Sign: [Short description]
   - **Trigger**: When this applies
   - **Instruction**: What to do instead
   - **Added after**: Session N - reason
   ```
3. **Move Forward** - Try different approach or next criterion
4. **Signal if Stuck** - `<ralph>GUTTER</ralph>` after 3 failures

---

## 0.7 Session Protocol

### Starting a Session

1. Read `RALPH_TASK.md` - Find unchecked criteria
2. Read `.ralph/guardrails.md` - Follow all active guardrails
3. Read `.ralph/progress.md` - Understand current state
4. Check `git log` - Review recent commits

### Ending a Session

1. Commit any pending work
2. Update `progress.md` with session summary
3. Push to remote
4. Note any blockers for next session

---

## 0.8 Logging Standards

### Log Format (JSON)

All applications should emit structured JSON logs with these fields:

```json
{
  "timestamp": "2026-02-02T00:15:32.123456Z",
  "level": "INFO",
  "message": "Operation completed",
  "logger": "{service}.services.{module}",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 234
}
```

### Log Levels

| Level | Usage |
|-------|-------|
| **DEBUG** | Detailed diagnostic information |
| **INFO** | Normal operations, business events |
| **WARNING** | Unexpected but recoverable situations |
| **ERROR** | Errors that prevented operation completion |
| **CRITICAL** | System-wide failures |

### Python Reference (Structlog)

```python
import structlog
from opentelemetry import trace

def configure_logging(log_level: str = "INFO", json_output: bool = True):
    """Configure structured logging with OpenTelemetry context."""
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_otel_context,  # Inject trace/span IDs
        structlog.processors.StackInfoRenderer(),
    ]
    
    if json_output:
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(processors=processors)

def add_otel_context(logger, method_name, event_dict):
    """Add OpenTelemetry trace context to every log event."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

---

## 0.9 Observability Standards

### Three Pillars

| Pillar | Tool | Purpose |
|--------|------|---------|
| **Logs** | Loki + Promtail | Structured JSON logs with trace correlation |
| **Metrics** | Prometheus | Counters, histograms, gauges |
| **Traces** | Tempo + OpenTelemetry | Distributed request tracing |

### Custom Metrics Patterns

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters - for events that only increase
OPERATIONS_TOTAL = Counter(
    "{service}_operations_total",
    "Total number of operations",
    ["status", "operation_type"]
)

# Histograms - for measuring durations/sizes
OPERATION_DURATION = Histogram(
    "{service}_operation_duration_seconds",
    "Duration of operations",
    ["operation_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Gauges - for values that can go up or down
QUEUE_SIZE = Gauge(
    "{service}_queue_size",
    "Current queue size",
    ["queue_name"]
)
```

### OpenTelemetry Setup

- Instrument: HTTP clients, database connections, cache operations
- Export to: OTLP endpoint (collector)
- Resource attributes: `service.name`, `service.version`

---

## 0.10 Security Standards

### Secrets Management

- Store all secrets in environment variables
- Use `SecretStr` type for secrets in configuration (Pydantic)
- Never log secrets or expose in error messages

```python
from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    SECRET_KEY: SecretStr
    DATABASE_URL: SecretStr
    API_KEY: SecretStr = SecretStr("")
    
    class Config:
        env_file = ".env"
```

### Security Checklist

- [ ] All secrets stored in environment variables
- [ ] Database credentials use strong passwords
- [ ] API keys have minimum required permissions
- [ ] TLS enabled for all external connections
- [ ] Session cookies marked as HttpOnly and Secure
- [ ] CORS configured to allow only trusted origins
- [ ] Rate limiting enabled on all endpoints
- [ ] Input validation on all user inputs
- [ ] Logs do not contain sensitive data
- [ ] Dependencies scanned for vulnerabilities

### API Security

| Requirement | Implementation |
|-------------|----------------|
| **Rate Limiting** | Per IP/user limits on all endpoints |
| **Input Validation** | Pydantic models with strict validation |
| **SQL Injection** | Parameterized queries via ORM |
| **XSS Prevention** | Content Security Policy headers |

---

## 0.11 Database Migration Standards

### Migration Principles

1. **Never modify existing migrations** - Always create new ones
2. **Always provide rollback** - Every `upgrade()` needs `downgrade()`
3. **Zero-downtime migrations** - Use multi-step approach for breaking changes
4. **Test migrations** - Run against copy of production data
5. **Backup before migration** - Always backup database first

### Zero-Downtime Patterns

**Adding non-nullable column (multi-step):**

```python
# Migration 1: Add column as nullable
def upgrade():
    op.add_column('table', sa.Column('new_col', sa.String(100), nullable=True))

# Migration 2: Backfill data
def upgrade():
    op.execute("UPDATE table SET new_col = 'default' WHERE new_col IS NULL")

# Migration 3: Add NOT NULL constraint
def upgrade():
    op.alter_column('table', 'new_col', nullable=False)
```

### Best Practices

| Practice | Description |
|----------|-------------|
| **Backup First** | Always backup database before running migrations |
| **Set Lock Timeout** | Set `lock_timeout` in migration scripts |
| **Test on Copy** | Run migrations against copy of production data first |
| **Batched Updates** | For large data migrations, use batched updates |
| **Concurrent Indexes** | Use `CREATE INDEX CONCURRENTLY` |

### Pre-Migration Checklist

```bash
# 1. Backup database
pg_dump -Fc $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).dump

# 2. Dry run migration
alembic upgrade head --sql > migration_preview.sql

# 3. Review the SQL before applying
```

---

## 0.12 API Design Standards

### Error Response Format

All API errors should use a consistent format:

```python
class ErrorResponse(BaseModel):
    error: str           # Error code/type
    message: str         # Human-readable message
    details: dict | None # Additional context
    request_id: str | None
```

### Custom Exception Hierarchy

```python
class AppException(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details

class NotFoundError(AppException):
    """Resource not found."""
    pass

class ValidationError(AppException):
    """Input validation failed."""
    pass

class ExternalServiceError(AppException):
    """External service call failed."""
    pass
```

### Pydantic Validation

- Use `Field()` for validation constraints
- Provide clear descriptions for API documentation
- Use enums for fixed choices

```python
from pydantic import BaseModel, Field
from enum import Enum

class Status(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    status: Status = Status.PENDING
    quantity: int = Field(1, ge=1, le=10000)
```

---

## 0.13 Versioning Standards

### Semantic Versioning: MAJOR.MINOR.PATCH

| Component | When to Increment |
|-----------|-------------------|
| **MAJOR** | Breaking API changes |
| **MINOR** | New features, backwards compatible |
| **PATCH** | Bug fixes, backwards compatible |

### Pre-release Tags

- Alpha: `1.0.0-alpha.1`
- Beta: `1.0.0-beta.1`
- Release Candidate: `1.0.0-rc.1`

---

## 0.14 Project Structure

### Recommended Directory Layout

```
project/
├── app/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Settings from environment
│   │
│   ├── api/                 # REST endpoints
│   ├── ui/                  # UI pages/components (if applicable)
│   ├── services/            # Business logic layer
│   ├── db/                  # Database layer
│   │   ├── database.py      # Engine/session setup
│   │   ├── models.py        # ORM models
│   │   └── crud/            # CRUD operations
│   ├── core/                # Cross-cutting concerns
│   │   ├── logging.py
│   │   ├── telemetry.py
│   │   └── exceptions.py
│   └── schemas/             # Pydantic models
│
├── migrations/              # Database migrations
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
├── docker/                  # Docker configuration
│
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 0.15 Tips for AI Agents

> **Common Pitfalls to Avoid**

### Logging
- Don't log sensitive data (passwords, API keys, tokens)
- Include correlation IDs (trace_id, request_id) in all logs
- Use structured logging, not string interpolation

### Database
- Never modify existing migration files
- Always test migrations on a data copy first
- Use transactions for multi-step operations

### API Design
- Validate all inputs with Pydantic
- Return consistent error formats
- Include request_id in error responses for debugging

### Testing
- Mock external services, don't call them in tests
- Use fixtures for database sessions with automatic rollback
- Keep tests independent - no shared state between tests

### Security
- Use `SecretStr` for sensitive configuration
- Never commit `.env` files
- Validate and sanitize all user inputs

---

## Navigation

- **Next:** [Executive Summary](01-executive-summary.md)
- **Task File:** [RALPH_TASK.md](../RALPH_TASK.md)
