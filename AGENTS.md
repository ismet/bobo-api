# bobo-api (epias-data-provider)

Minimal FastAPI service that wraps [eptr2](https://github.com/Tideseed/eptr2) for EPİAŞ power-plant listing, market clearing prices, and real-time generation.

## Commands

| Command | Effect |
|---|---|
| `pip install -e ".[dev]"` | Install app + dev deps (pytest, httpx) |
| `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | Dev server |
| `pytest` | Run all tests |
| `pytest -m "not integration"` | Skip live EPİAŞ calls |

No linter, formatter, or typechecker is configured — `pytest` is the only verification gate.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# No .env.example (README still says `cp .env.example .env` — stale) — create .env with:
#   EPTR_USERNAME=...
#   EPTR_PASSWORD=...
```

No `.gitignore` exists in this package — watch for `.env`, `__pycache__/`, `.venv/`, `epias_data_provider.egg-info/`, and **`.eptr2-tgt`** (eptr2 TGT token JSON written by `recycle_tgt=True`; credential artifact — never commit).

If `pytest` fails with `No module named '_pytest'`, the `.venv` symlinks have drifted from its build Python — recreate it (`python3 -m venv .venv && pip install -e ".[dev]"`).

Run everything from the repo root: `Settings` reads `env_file=".env"` and eptr2 writes `.eptr2-tgt` to `tgt_path` (both default `.` — cwd-relative). Only `tests/conftest.py` loads `.env` by absolute path, so `pytest` survives other cwds; `uvicorn` does not.

## Key details

- **Python >=3.11**, FastAPI, pydantic-settings. `.env` is read twice: pydantic-settings for `API_KEY`/`CORS_ALLOW_ORIGINS`, and eptr2's **own** parser (it does not use python-dotenv — `pip show eptr2` shows only `pytz, urllib3`) which reads `EPTR_USERNAME`/`EPTR_PASSWORD` and sets them as env vars. Also, `tests/conftest.py` imports `dotenv` directly, but **`python-dotenv` is not a declared dependency** (`pyproject.toml`) — it only works because pydantic-settings pulls it in transitively. Don't remove pydantic-settings without declaring `python-dotenv`.
- **eptr2 credentials**: Set `EPTR_USERNAME` / `EPTR_PASSWORD` in `.env` (required for any data endpoint).
- **API key auth**: Optional — set `API_KEY` to require `X-API-Key` header on `/power-plants` routes. Unset/empty = no auth.
- **CORS**: Default allows `localhost` / `127.0.0.1` on any port. Set `CORS_ALLOW_ORIGINS` (comma-separated) for deployed frontends.
- **Endpoints**:
  - `GET /health` — liveness (no API key)
  - `GET /power-plants` — plant list
  - `GET /power-plants/{id}/prices-and-generation?start_date=…&end_date=…` — hourly `prices` (MCP) + `powers` (generation) aligned pairwise: only hours where **both** exist land in the arrays; the rest are listed in `missing_price_dates` / `missing_power_dates`. `end_date` must be strictly before today in Europe/Istanbul. Fetches two upstream datasets: `mcp` chunked at **31** days (defensive; `_MCP_CHUNK_DAYS`) and `rt-gen` at **89** days (`_RT_GEN_CHUNK_DAYS`).

## Tests

- **Unit/mocked** (default): `pytest -m "not integration"` — uses `TestClient` with mocked eptr. Tests skip API key enforcement.
- **Integration**: `pytest -m integration` — calls live EPİAŞ; auto-skipped when `EPTR_USERNAME`/`EPTR_PASSWORD` are unset. Plain `pytest` runs both. `conftest.py` loads `.env` from repo root and clears `API_KEY` automatically.

## Architecture

```
app/main.py ← app/routers/plants.py ← app/epias_service.py ← app/eptr_client.py
                                    ↕
                               app/schemas.py
```

- `chunking.py` — `iter_date_chunks` window splitting (default 89 days; MCP overrides to 31 in `epias_service.py`)
- `deps.py` — FastAPI dependency injection (auth, DB-less)
- `config.py` — pydantic-settings `Settings` from `.env`
- `eptr_client.py` — thread-safe **singleton** `EPTR2` client with TGT recycling. Unit tests inject a fake via `app.dependency_overrides[get_eptr]` (the real client is never built); `reset_eptr_client()` is only used by the integration suite's autouse fixture to force a fresh client per test.
- Returned `prices` use field name `priceEur` in EPTR; may be TL/MWh, not EUR (documented in OpenAPI).
