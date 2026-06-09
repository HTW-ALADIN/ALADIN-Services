# sql-query-generation

To use this application add a .env file in the root level with the following key: `OPENAI_API_KEY={Add OpenAI key here}`

Run the application with the command: `npx ts-node src/index.ts`

## Docker

```bash
# Build the image
docker build -t sql-assessment-service .

# Run (PostgreSQL-only mode — no PGlite needed)
docker run -p 3000:3000 sql-assessment-service

# Run with OpenAI key
docker run -p 3000:3000 -e OPENAI_API_KEY=sk-... sql-assessment-service
```

PGlite works out of the box inside the container — no external database required. The `@electric-sql/pglite` package (including its WASM binary) is copied into the image separately from the bundle because esbuild cannot inline WASM files.

```bash
# Run with a pre-loaded PGlite schema (HTTP API mode)
docker run -p 3000:3000 \
  -e PGLITE_INIT_SQL_FILE=/data/schema.sql \
  -v /local/path/schema.sql:/data/schema.sql \
  sql-assessment-service
```

To start a local PostgreSQL alongside the service:

```bash
docker compose up
```

The `docker-compose.yml` spins up a Postgres container. Uncomment the `app` service block to also run the API in Docker.

## PostgreSQL (external database)

Database Analysis: Call the POST API:
`http://localhost:3000/api/database/analyze-database`

with the following DTO in the body:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "{DatabaseHost}",
		"port": "{DatabasePort}",
		"username": "{DatabaseUserName}",
		"password": "{DatabasePassword}",
		"database": "{DatabaseName}",
		"schema": "{SchemaName}"
	}
}
```

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	}
}
```

## PGlite (in-process, no external database required)

PGlite embeds a full PostgreSQL engine in-process. No server, no credentials — just pass your DDL + seed SQL and a unique `databaseId`. The instance is kept alive in memory for the lifetime of the service process.

> **Auto-analyze**: The four endpoint groups (`/api/generation`, `/api/grading`, `/api/description`, `/api/query`) will **automatically** run the analyze step when `sqlContent` is present in the `connectionInfo`. This means a separate call to `/api/database/analyze-database` is **not required** — each request can be fully self-contained.

### Pre-loading a schema via `PGLITE_INIT_SQL_FILE` / `--init-sql-file`

Instead of including `sqlContent` in every request, you can point the service at a SQL file that will be used as the default `sqlContent` for **any** PGlite request where `sqlContent` is absent from the request body.

| Method | How to set |
|---|---|
| Environment variable (HTTP API / Docker) | `PGLITE_INIT_SQL_FILE=/path/to/schema.sql` |
| CLI flag | `--init-sql-file /path/to/schema.sql` |

**Priority**: an explicit `sqlContent` in the request body always takes precedence over the configured file.

**Error behaviour**: if the configured path does not exist the service returns `500` for that request; all other requests are unaffected.

**Example — CLI:**
```bash
npx ts-node src/cli/index.ts --init-sql-file ./schema.sql generation:generate '{"connectionInfo":{"type":"pglite","databaseId":"mydb"}}'
```

**Example — Docker:**
```bash
docker run -p 3000:3000 \
  -e PGLITE_INIT_SQL_FILE=/data/schema.sql \
  -v /local/path/schema.sql:/data/schema.sql \
  sql-assessment-service
```

After starting with `PGLITE_INIT_SQL_FILE`, you can omit `sqlContent` from every request body:

```json
{
    "connectionInfo": {
        "type": "pglite",
        "databaseId": "my-db"
    },
    "query": "SELECT * FROM products"
}
```



### 1. Analyze (register) a PGlite database (explicit, optional)

Call `POST /api/database/analyze-database` with `type: "pglite"`:

```json
{
	"connectionInfo": {
		"type": "pglite",
		"databaseId": "my-db",
		"sqlContent": "CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));\nINSERT INTO products (name, price) VALUES ('Widget', 9.99);"
	}
}
```

| Field | Required | Description |
|---|---|---|
| `type` | ✓ | Must be `"pglite"` |
| `databaseId` | ✓ | Arbitrary string key used to reference this instance in all subsequent calls |
| `sqlContent` | ✓ | Full DDL + optional seed DML executed once on a fresh in-memory PG instance |

Calling this endpoint again with the same `databaseId` replaces the existing instance.

### 2. Execute a query against a PGlite database

**Self-contained (recommended)** — include `sqlContent` directly in the request body; no separate analyze call needed:

```json
{
	"connectionInfo": {
		"type": "pglite",
		"databaseId": "my-db",
		"sqlContent": "CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));\nINSERT INTO products (name, price) VALUES ('Widget', 9.99);"
	},
	"query": "SELECT * FROM products"
}
```

**After a prior `analyze-database` call** — omit `sqlContent` to reuse the already-registered instance:

```json
{
	"connectionInfo": {
		"type": "pglite",
		"databaseId": "my-db"
	},
	"query": "SELECT * FROM products"
}
```

Only SELECT statements are accepted; INSERT / UPDATE / DELETE / DDL are rejected with 400.

## Task Generation

Call `POST /api/generation/generate` with the following body:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"taskConfiguration": {
		"aggregation": false,
		"columnCount": 2,
		"predicateCount": 2,
		"operationTypes": [],
		"joinDepth": 2,
		"joinTypes": [],
		"groupby": false,
		"having": false,
		"orderby": true
	}
}
```

The endpoint will automatically register the database schema if it has not been registered yet (auto-analyze). Subsequent calls within the same process skip the expensive round-trip.

What is possible to fill out in the configuration parameters can be found in interfaces.ts/ITaskConfiguration.

## Grading

Call `POST /api/grading/grade` with the following body:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"gradingRequest": {
		"taskId": "4f7c66ed-e4e5-422e-8d6f-ef4ee3876d07",
		"studentQuery": "SELECT character.kindid, character.genderid FROM public.couple INNER JOIN public.character ON couple.femaleid = character.characterid INNER JOIN public.kind ON character.kindid = kind.kindid WHERE kind.kindid >= 1 AND kind.kindid <= 4    OR character.characterid = 108 ORDER BY couple.femaleid ASC"
	}
}
```

The endpoint will automatically register the database schema if it has not been registered yet (auto-analyze). Subsequent calls within the same process skip the expensive round-trip.

## Description

Call any of the following endpoints under `/api/description/`:

- `POST /api/description/template`
- `POST /api/description/llm/default`
- `POST /api/description/llm/creative`
- `POST /api/description/llm/multi-step`
- `POST /api/description/hybrid`

**PostgreSQL** — auto-analyze on first call:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"query": "SELECT * FROM products WHERE price > 10"
}
```

**PGlite** — self-contained (include `sqlContent`):

```json
{
	"connectionInfo": {
		"type": "pglite",
		"databaseId": "my-db",
		"sqlContent": "CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));\nINSERT INTO products VALUES (1, 'Widget', 9.99);"
	},
	"query": "SELECT name, price FROM products WHERE price > 5"
}
```

The description endpoints only require the registered schema metadata, not a live database connection — making them fully compatible with PGlite.

