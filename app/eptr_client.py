from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

from app.config import Settings

if TYPE_CHECKING:
    from eptr2 import EPTR2

_lock = Lock()
_instance: EPTR2 | None = None
_settings: Settings | None = None


def get_eptr(settings: Settings | None = None) -> EPTR2:
    """Singleton EPTR2 client with TGT recycling (thread-safe lazy init)."""
    global _instance, _settings
    if settings is not None:
        _settings = settings
    if _settings is None:
        _settings = Settings()

    if _instance is not None:
        return _instance

    with _lock:
        if _instance is not None:
            return _instance
        from eptr2 import EPTR2

        s = _settings
        _instance = EPTR2(
            use_dotenv=True,
            recycle_tgt=True,
            dotenv_path=str(s.eptr_dotenv_resolved),
            tgt_path=s.eptr_tgt_path,
        )
        return _instance


def reset_eptr_client() -> None:
    """Clear cached client (for tests)."""
    global _instance, _settings
    with _lock:
        _instance = None
        _settings = None
