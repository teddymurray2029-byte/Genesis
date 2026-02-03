# Genesis

Genesis is a multi-language research prototype exploring a multi‑octave memory system. The repository combines Python pipelines for FFT-based encoding and storage, a FastAPI backend with streaming visualization, a Svelte UI, and a small Rust library for categorical type system experiments. A lightweight Node CLI helps launch the services.

> **Status**: Work in progress. The Node CLI currently implements only the `service` command; other commands are stubs.

---

## Repository map

- **Python memory pipeline**: FFT encoders/decoders, triplanar projection, and multi‑octave orchestration in `src/pipeline/` and `src/memory/`.
- **WaveCube integration**: Layered 3D storage and compression utilities under `lib/wavecube/` with a bridge in `src/memory/wavecube_integration.py`.
- **Visualization backend**: FastAPI service with health, log CRUD, and WebSocket streaming in `src/visualization/server.py`.
- **SQL API + MySQL gateway**: JSON-backed GenesisDB in `src/api/log_api.py` and a MySQL protocol gateway in `src/api/mysql_server.py`.
- **Frontend UI**: Svelte + Vite visualization app in `ui/`.
- **Rust library**: Categorical type system scaffolding in `src/lib.rs` and `src/category/`.
- **Node CLI**: `genesis.js` wraps and launches Python services.

---

## Quick start (Docker Compose)

```bash
docker compose up --build
```

This starts:
- Visualization backend on `http://localhost:8000`
- SQL API on `http://localhost:8080` (matches the UI default)
- UI on `http://localhost:5173`

Optional MySQL-compatible gateway:

```bash
docker compose --profile mysql up --build
```

Environment variables:
- `GENESIS_DB_PATH` (default: `./data/genesis_db.json`)
- `GENESIS_MYSQL_HOST` (default: `0.0.0.0`)
- `GENESIS_MYSQL_PORT` (default: `3306`)

---

## Prerequisites (local development)

- Python 3.10+
- Node.js 18+
- Rust (optional, only if building the Rust library)

Install Node dependencies at the repo root before using the CLI:

```bash
npm install
```

---

## Local setup

### 1) Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 2) Run the visualization backend

```bash
node genesis.js service --host 0.0.0.0 --port 8000
```

The service exposes:
- `GET /health` (or `/api/health`)
- `GET/POST/PUT/DELETE /logs`
- `WS /ws`

### 3) Run the visualization UI

```bash
npm --prefix ui install
npm --prefix ui run dev
```

The UI expects the backend at `http://localhost:8000`.

---

## SQL API + MySQL gateway (standalone)

### SQL API

```bash
export GENESIS_DB_PATH=./data/genesis_db.json
uvicorn src.api.log_api:app --host 0.0.0.0 --port 8080
```

### MySQL-compatible gateway

```bash
export GENESIS_DB_PATH=./data/genesis_db.json
export GENESIS_MYSQL_HOST=0.0.0.0
export GENESIS_MYSQL_PORT=3306
python -m src.api.mysql_server
```

---

## Examples

```bash
python examples/demo_fft_roundtrip.py
python examples/demo_memory_integration.py
python examples/demo_hierarchical_synthesis.py
```

---

## CLI status

`genesis.js` exposes several commands, but only the visualization `service` command is currently implemented. The other commands parse arguments and exit with a "not yet implemented" message.

---

## Tests

```bash
pytest tests/ -v
```

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
