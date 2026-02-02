# Genesis

Genesis is an experimental, multi-language research prototype for a multi‑octave memory system. The repository combines Python prototypes for FFT-based encoding and memory storage, a FastAPI backend for visualization and SQL access, a Svelte UI for live visualization, and a small Rust library for categorical type system experiments.

> **Status**: Work in progress. The JavaScript CLI currently implements only the `service` command; the other commands are stubs that print a "not yet implemented" message.

---

## What’s in this repo

- **Python memory pipeline**: FFT encoders/decoders, triplanar projection, and multi‑octave orchestration in `src/pipeline/` and `src/memory/`.
- **WaveCube integration**: Layered 3D storage and compression utilities under `lib/wavecube/` with a bridge in `src/memory/wavecube_integration.py`.
- **Visualization backend**: FastAPI service with health, log CRUD, and WebSocket streaming in `src/visualization/server.py`.
- **SQL API + MySQL gateway**: JSON-backed GenesisDB with a SQL-like API in `src/api/log_api.py` and a MySQL protocol gateway in `src/api/mysql_server.py`.
- **Frontend UI**: Svelte + Vite visualization app in `ui/`.
- **Rust library**: Categorical type system scaffolding in `src/lib.rs` and `src/category/`.
- **Node CLI**: `genesis.js` wraps and launches Python services (only the `service` command is implemented right now).

---

## Quick start

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

The UI expects the visualization backend at `http://localhost:8000`.

---

## SQL API + MySQL gateway

### SQL API

```bash
export GENESIS_DB_PATH=./data/genesis_db.json
uvicorn src.api.log_api:app --host 0.0.0.0 --port 8001
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
