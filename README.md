# EPİAŞ data provider

Minimal FastAPI service that calls [eptr2](https://github.com/Tideseed/eptr2) for power plant listing, market clearing prices (MCP), and plant-scoped real-time generation.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env with EPTR_USERNAME / EPTR_PASSWORD
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On Render or any host that injects `PORT`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

**Auth:** If you set `API_KEY` in `.env`, protectable routes require header `X-API-Key: <same value>`. Leave `API_KEY` unset or empty to disable (local dev).

**CORS:** With no `CORS_ALLOW_ORIGINS`, browsers may call the API only from `http://localhost` / `http://127.0.0.1` on any port. Set `CORS_ALLOW_ORIGINS` to a comma-separated list (e.g. `https://your-frontend.onrender.com`) when a deployed frontend needs access.

## Deploy on Render

Python is pinned with [`.python-version`](.python-version) (`3.14.3`). Create a Web Service from this repo (free tier is declared in [`render.yaml`](render.yaml)) or paste equivalent settings:

- **Build:** `pip install --upgrade pip && pip install .`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`

Set **`EPTR_USERNAME`** and **`EPTR_PASSWORD`** in the Render dashboard (same as local `.env`; no `.env` file is required on the server). Optionally set **`API_KEY`** so `/power-plants` routes require `X-API-Key`.

Optionally set **`CORS_ALLOW_ORIGINS`** if a browser app calls this API from non-localhost origins.

Free instances spin down after idle traffic and wake on request (cold starts).

- `GET /health` — liveness (no API key)
- `GET /power-plants` — power plant list (`id`, `name`, `eic`, `shortName`)
- `GET /power-plants/{pp_id}/prices-and-generation?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — aligned hourly series: `prices` (MCP / `priceEur` semantics from EPTR; see OpenAPI) and `powers` (generation) only for hours where **both** exist; `missing_price_dates` / `missing_power_dates` list hour starts without price or power respectively (`YYYY-MM-DD HH:mm:ss`, Europe/Istanbul). Counts: `num_total_hours`, `num_missing_hours`, `num_items`.

`end_date` must be strictly before “today” in `Europe/Istanbul`. Real-time generation is fetched in chunks of at most 89 days per upstream limits.

## Tests

```bash
pytest
```

Loads `.env` from the repo root so integration tests can run when `EPTR_USERNAME` / `EPTR_PASSWORD` are set (live EPİAŞ calls). Markers: `integration` (auto-skipped without credentials).
