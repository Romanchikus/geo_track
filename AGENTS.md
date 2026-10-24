# Agent Instructions

## ALL PROJECTS

- Never run `git commit`, `git push`, or rewrite Git history.
- Keep code simple and readable.
- Split large logic into small, focused modules and functions.
- Use simple, descriptive names.
- Add tests whenever behavior can reasonably be tested.
- Add only short docstrings for public or non-obvious methods.
- Always add useful logging around important operations and failures.
- Never log secrets, tokens, passwords, cookies, or sensitive data.
- Do not over-engineer or add abstractions without a reason.

## BACKEND

- Use async DB access with async FastAPI code.
- Keep routers thin.
- Put business logic in services/use-cases.
- Put complex DB queries in repositories/query services.
- A new HTTP area gets a new file under `app/api/routers/`.
- Keep transactions at the endpoint/use-case boundary.
- Do not hold DB transactions during CPU work, external calls, or unrelated I/O.
- Use SQLAlchemy `select()`; never use the legacy `Query` API.
- Use Alembic for DB migrations.
- Avoid unnecessary `Optional`/nullable variables, especially in DB code.
- Separate authentication from authorization.
- Keep auth dependencies focused:
  - current user only when only the user is needed;
  - user + related data when related data is required.
- Fetch required related data efficiently instead of creating repeated queries.
- Use `Protocol`/interfaces for replaceable external dependencies.
- Avoid synchronous/blocking libraries in async request paths.
- Use `asyncio.gather()` for independent async I/O when appropriate.
- Never concurrently use the same DB session/transaction with `asyncio.gather()`.
- Use bounded concurrency for large numbers of tasks.
- Put external integrations behind clients/adapters.
- Always use explicit HTTP timeouts.

## API

- Keep endpoints small.
- Do not put business logic in routers.
- Use reusable filtering/query models or filtering libraries instead of repeating many filter parameters in endpoint signatures.
- Validate input at the API boundary.
- Keep API schemas separate from DB models.
- Use consistent HTTP status codes and error responses.

## DATA

- Use `dataclass(slots=True)` for suitable internal data structures.
- Use NumPy/Pandas for appropriate large numerical/tabular operations.
- Do not load data into memory unnecessarily.
- Use generators/lazy iteration when only the next values are needed.
- Use context managers for resources that require deterministic cleanup.
- Pickle only trusted/internal Python data.
- Never unpickle untrusted data.
- For very large data, prefer streaming/chunking.

## DATABASE

- Use async SQLAlchemy sessions.
- Keep transaction ownership explicit.
- Commit at the endpoint/use-case transaction boundary.
- Do not commit inside generic query/repository methods unless that method explicitly owns the transaction.
- Use `select()` and modern SQLAlchemy APIs.
- Prevent N+1 queries.
- Add indexes based on real query patterns.
- Use Alembic migrations for schema changes.
- Integration-test DB queries against real PostgreSQL.
- Test transaction rollback behavior.

## TESTING

- Test important business rules.
- Test success and failure paths.
- Test authorization.
- Test DB queries with real PostgreSQL integration tests.
- Test transaction rollback.
- Avoid excessive mocking of database behavior.
- Keep tests deterministic.

## PROJECT STRUCTURE

Prefer:

```
app/
├── api/
│   ├── routers/
│   └── dependencies.py
├── services/
├── db/
│   ├── models/
│   ├── repositories/
│   └── session.py
├── schemas/
├── clients/
├── workers/
├── core/
└── main.py
```

Adapt the structure when the project is small; do not create unnecessary layers.

# Rules

- NEVER git commit, push, or rewrite Git history.
- Keep code simple; use simple names.
- Split large logic into small modules/functions.
- Keep routers thin; business logic → services/use-cases.
- Complex DB queries → repositories/query services.
- New HTTP area → new `app/api/routers/<area>.py`.
- Async FastAPI → async DB access.
- Transactions belong at the endpoint/use-case boundary.
- Never hold DB transactions during CPU work, external calls, or unrelated I/O.
- SQLAlchemy: use `select()`, not legacy `Query`.
- DB schema changes → Alembic migrations.
- Separate authentication and authorization.
- Keep auth dependencies focused; fetch related data efficiently when required.
- Avoid unnecessary `Optional`/nullable DB values.
- External dependencies → clients + Protocol/interfaces when useful.
- Avoid blocking/synchronous libraries in async paths.
- `asyncio.gather()` for independent I/O; NEVER concurrently share a DB session.
- Use filtering/query models instead of many repeated endpoint filter parameters.
- `dataclass(slots=True)` for suitable internal structures.
- NumPy/Pandas for appropriate large numerical/tabular work.
- Prefer streaming/generators/lazy iteration for data not needed immediately.
- Pickle only trusted internal data; never unpickle untrusted data.
- Always add useful logging; never log secrets.
- Add short docstrings only for public/non-obvious methods.
- Add tests whenever practical.
- Integration-test DB queries against real PostgreSQL.
- Test transaction rollback.
- Do not over-engineer.

# Monorepo

Follow `AGENTS.md` at this root. It is the rule set for every service.

- One directory per service. Each service has its own `app/` and the package `AGENTS.md` files.
- Do not import one service from another. Call it through a client.
- Shared code is its own package. It does not depend on a service.
- Do not run `git commit`, `git push`, or rewrite Git history.
- Adapt the layout when a service is small. Do not add empty layers.
