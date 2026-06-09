# Graph Rewriting As A Service

## Prerequisites

This repository contains all files necessary to run the application in local development and production environments.
It requires Docker and Node.js 22+ on your system.

When cloning this repository and opening it through VSCode, it will ask you to install all recommended VSCode extensions.

## Getting started

In order to install and run this application in your local development environment, you first need to install all dependencies via npm

    npm install

Next an .env file should be created by copying the .env.example and setting the appropriate values.

### Development Environment

The application supports two database backends:

#### In-Memory (default, no Neo4j needed)

Simply start the application — no external database required:

```bash
npm run dev
```

#### With Neo4j

To run with Neo4j as the database backend:

1. Start Neo4j container:
    ```bash
    docker compose -f docker-compose.dev.yml up
    ```

2. In another terminal, start the application with neo4j backend:
    ```bash
    DB_BACKEND=neo4j npm run dev
    ```

If using VSCode you can instead run the VSCode-Task `Start dev environment` as a shortcut.

### Production Environment (Docker + Compose)

To run the application in production using Docker containers:

```bash
# Set required environment variables
export NEO4J_PASSWORD=your-secure-password

# Start both Neo4j and the application service
docker compose -f docker-compose.prod.yml up -d
```

The application will be available at `http://localhost:8080`.  
Neo4j Browser is accessible at `http://localhost:7474`.

**Note:** As of this version, the Docker image is split into two services:
- `graph-rewriting-service`: Node.js API server (port 8080)
- `neo4j`: Graph database (ports 7687 for Bolt, 7474 for Browser)

This separation reduces image size and enables independent scaling.

## Architecture

### Build Pipeline

- `npm run build` now bundles the service with esbuild.
- `npm run typecheck` runs TypeScript checks without emitting files.
- The build emits bundled artifacts to `dist/index.js` and `dist/cli.js`.
- Static assets from `src/static` are copied to `dist/static` during the build.

### Docker Images

- **graph-rewriting-service**: Lightweight Node.js container based on `node:22-alpine`
  - Runs the Fastify HTTP API
  - Connects to Neo4j via environment variables
  - Contains bundled runtime artifacts only (no `node_modules` in the final image)
  - No embedded database or process manager

- **neo4j** (from official image): Graph database service
  - Provides pattern matching and graph transformation operations
  - Can be deployed separately or in the same compose stack

### Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `APP_ENV` | `production` | No | Application environment: `development`, `production` |
| `DB_BACKEND` | `memory` | No | Database backend: `memory` (in-memory, no external DB) or `neo4j` |
| `NEO4J_URI` | `bolt://neo4j:7687` | No | Neo4j Bolt connection URI (only when `DB_BACKEND=neo4j`) |
| `NEO4J_USERNAME` | `neo4j` | No | Neo4j username (only when `DB_BACKEND=neo4j`) |
| `NEO4J_PASSWORD` | (none) | When neo4j | Neo4j password (must be set when using neo4j backend) |

## Documentation

For documentation of the rewrite and instantiation rules, please refer to the [Wiki](https://github.com/sonjaka/graph-rewriting-as-a-service/wiki).

## Demos

The demos and examples use .http files to define example requests that can be sent to the development server.
These can be run from VS Code with the [httpYak VSCode Extension](https://marketplace.visualstudio.com/items?itemName=anweber.vscode-httpyac). IntenlliJ natively supports http files.
httpYak also provides a CLI tool: [httpYak on the CLI](https://httpyac.github.io/guide/installation_cli.html).

### Demos

This repository contains three demos for graph rewriting requests.
They can be found in the /demo folder.

#### Sierpinsky-Triangles

Creates the third generation of a sierpinsky triangle through simple transformation rules.
A simple http-File to execute and send to the server.

#### UML to Petrinet

Genereates a Petrinet from the given UML diagram hostgraph and transformations rules.
A simple http-File to execute and send to the server

#### TicTacToe

A very simple TicTacToe game againt a computer player powered by graph transformations.
This testcase consists of a very basic web app built on the Vue.js Framework.
You can install the project by first running `npm install`, then `npm run dev`.

## Testing

### Unit Tests

```bash
npm test
```

### Smoke Tests

End-to-end smoke tests using `curl` against a running service.

#### Memory backend only (no external dependencies)

```bash
make smoke-test
```

#### Memory + Neo4j backend

Start a Neo4j container first, then run the smoke test with Neo4j credentials:

```bash
# Start Neo4j
NEO4J_USERNAME=neo4j NEO4J_PASSWORD=<your-password> \
  docker compose -f docker-compose.dev.yml up -d neo4j

# Run smoke tests for both backends
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD=<your-password> \
  make smoke-test
```

When `NEO4J_URI` is not set, the Neo4j portion of the smoke test is skipped automatically.

#### Teardown

```bash
docker compose -f docker-compose.dev.yml down
```

## SwaggerUI / OpenAPI

When the server is running, you can access the SwaggerUI / OpenAPI documentation via the following url:

https://<api_host>:<api_port>/documentation
