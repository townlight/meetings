from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path

import pytest

SIBLING_TOWNLIGHT_CORE = Path(__file__).resolve().parents[1].parent / "core"
if SIBLING_TOWNLIGHT_CORE.is_dir() and str(SIBLING_TOWNLIGHT_CORE) not in sys.path:
    sys.path.insert(0, str(SIBLING_TOWNLIGHT_CORE))
if SIBLING_TOWNLIGHT_CORE.is_dir():
    import townlight_core
    import townlight_core.auth

    townlight_core_path = str(SIBLING_TOWNLIGHT_CORE / "townlight_core")
    townlight_core_auth_path = str(SIBLING_TOWNLIGHT_CORE / "townlight_core" / "auth")
    if townlight_core_path not in townlight_core.__path__:
        townlight_core.__path__.append(townlight_core_path)
    if townlight_core_auth_path not in townlight_core.auth.__path__:
        townlight_core.auth.__path__.append(townlight_core_auth_path)

from townlight_meetings.main import STAFF_AUTH_MODE_ENV_VAR, STAFF_OPEN_MODE


if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(autouse=True)
def explicit_open_mode_for_legacy_feature_tests(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    if request.node.get_closest_marker("uses_townlight_meetings_default_staff_mode"):
        monkeypatch.delenv(STAFF_AUTH_MODE_ENV_VAR, raising=False)
        return
    monkeypatch.setenv(STAFF_AUTH_MODE_ENV_VAR, STAFF_OPEN_MODE)
