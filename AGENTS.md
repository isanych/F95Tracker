# AGENTS.md

## Database Schema Versioning

The database uses a versioned migration system defined in `db.py`.

### How it works

- **`SCHEMA_VERSION`** constant in `db.py` defines the current expected schema version (currently `2`).
- The `settings` table stores a `schema_version` column tracking the DB's actual version.
- On app startup, `init_db()` calls `_run_migrations()` which:
  1. Detects the current DB version via `_get_db_version(conn)`
  2. If the DB version is `0` (no tables), runs migration `1` to create the initial schema
  3. If the DB version is lower than `SCHEMA_VERSION`, runs each migration in order
  4. Adds the `schema_version` column if missing (idempotent)
  5. Updates `schema_version` to `SCHEMA_VERSION`

### Adding a new migration

When modifying the database schema:

1. Bump `SCHEMA_VERSION` by 1 in `db.py`
2. Add a new migration function decorated with `@migration(N)` where `N` is the new version number
3. The migration receives an `aiosqlite.Connection` and should be idempotent (use `try/except` for `ALTER TABLE` since the column may already exist)
4. New columns should also have their `DEFAULT` value set in the `ALTER TABLE` statement
5. Do **not** modify the v1 initial schema migration to include new columns — only add new migrations

Example migration:

```python
@migration(3)
async def _migrate_v2_to_v3(conn):
    """Add new_column to games table."""
    try:
        await conn.execute(
            "ALTER TABLE games ADD COLUMN new_column TEXT DEFAULT ''"
        )
        await conn.commit()
    except aiosqlite.OperationalError:
        await conn.commit()
```

### Version detection logic

`_get_db_version()` determines the version as follows:
- If the `settings` table doesn't exist → version `0` (fresh DB)
- If the `settings` table exists but has no `schema_version` column → version `1` (pre-versioning DB)
- Otherwise → read `schema_version` from the `settings` row

## Code style

- Python backend: async/await with aiosqlite, FastAPI
- Frontend: Alpine.js + HTMX + Jinja2 templates
- When passing JSON data to Alpine.js components, use `<script>` tags with global variables instead of inline `x-data="func({{ data | tojson }})"` to avoid HTML attribute escaping issues.