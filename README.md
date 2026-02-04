# Genesis GraphQL Gateway (Draft)

Genesis is a research prototype exploring a multi‑octave memory system with a SQL-backed data layer, streaming visualization, and a Svelte UI. This README reframes the project around a **GraphQL-first API** for working with entries, logs, and metadata, while calling out what is available today and what remains a draft.

> **Status**: The GraphQL layer is **not yet implemented**. The current, working API is the SQL/REST service described below. This document defines the target GraphQL surface and how it maps to existing capabilities.

---

## Why GraphQL here?

Genesis exposes heterogeneous data (entries, logs, voxel clouds) that benefit from:

- **Flexible selection**: Clients request only the fields they need.
- **Consistent schema**: Typed objects for entries, logs, and system status.
- **Composable UI data**: A single query can hydrate multiple panels in the UI.

---

## Current API (available now)

Genesis ships a FastAPI service with SQL-style querying and metadata endpoints.

### Core endpoints

- `GET /health` → service status and counts
- `GET /schema` → `entries` table schema
- `POST /query` → SQL against `entries` or `logs`
- `POST /reload` → reload the data source

### Example SQL query (today)

```bash
curl -X POST http://localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT * FROM entries LIMIT 5"}'
```

---

## GraphQL API (draft design)

> These queries and types describe the **intended** GraphQL interface. They are a design target and not yet executable.

### Proposed schema (excerpt)

```graphql
type Query {
  health: Health!
  entries(limit: Int, offset: Int, orderBy: EntryOrder): [Entry!]!
  logs(limit: Int, offset: Int, level: LogLevel): [Log!]!
  entry(id: ID!): Entry
}

type Health {
  status: String!
  entries: Int!
  voxelCloudPath: String
  dbPath: String
}

type Entry {
  id: ID!
  timestamp: String
  label: String
  payload: JSON
}

type Log {
  id: ID!
  level: String
  message: String
  timestamp: String
}
```

### Example GraphQL query (draft)

```graphql
query Dashboard {
  health {
    status
    entries
  }
  entries(limit: 5, orderBy: { field: "timestamp", direction: DESC }) {
    id
    label
    timestamp
  }
}
```

### Mapping to the current SQL API

- `health` → `GET /health`
- `entries` / `entry` → `POST /query` against the `entries` table
- `logs` → `POST /query` against the `logs` table

---

## Quick start (Docker Compose)

```bash
docker compose up --build
```

Services:
- Visualization backend: `http://localhost:8000`
- SQL API (current): `http://localhost:8080`
- UI: `http://localhost:5173`

Optional MySQL-compatible gateway:

```bash
docker compose --profile mysql up --build
```

---

## Local development

### Prerequisites

- Python 3.10+
- Node.js 18+
- Rust (optional, for the Rust library)

### Install dependencies

```bash
python -m pip install -r requirements.txt
npm install
```

### Run the SQL API

```bash
export GENESIS_DB_PATH=./data/genesis_db.json
uvicorn src.api.log_api:app --host 0.0.0.0 --port 8080
```

### Run the visualization backend

```bash
node genesis.js service --host 0.0.0.0 --port 8000
```

### Run the UI

```bash
npm --prefix ui install
npm --prefix ui run dev
```

---

## Roadmap to GraphQL

1. Add a GraphQL server (FastAPI + Strawberry or Ariadne).
2. Implement resolvers that translate to existing `entries`/`logs` SQL queries.
3. Add subscriptions for live log streaming over WebSockets.
4. Update the UI to query the GraphQL endpoint.

---

## Documentation

- `ARCHITECTURE.md` – Technical architecture notes
- `WHITEPAPER.md` – Research write-up
- `DEPLOYMENT.md` – Deployment notes
- `CONTRIBUTING.md` – Contribution guidelines
- `docs/FFT_ARCHITECTURE_SPEC.md` – FFT specification

---

## License

MIT License. See `LICENSE`.
