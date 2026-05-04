from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.routers import plants as plants_router

_LOCALHOST_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app = FastAPI(
    title="EPİAŞ data provider",
    version="0.1.0",
    description=(
        "Market clearing prices use JSON field `priceEur`; values are taken from EPTR2 MCP "
        "and may be TL/MWh rather than EUR."
    ),
)

_settings = Settings()
_cors_origins = _settings.cors_allow_origins_list()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_LOCALHOST_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(plants_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
