from fastapi import APIRouter

from churn_platform.presentation.api.dependencies import (
    ENGINE_MODES,
    api_key_configured,
    default_engine_mode,
    qwen_cooling_down,
    qwen_last_reason,
)

router = APIRouter(prefix="/engine", tags=["Engine"])


@router.get("/status")
async def engine_status():
    """
    What the dashboard needs to explain which scoring engine will run, and why.

    The local engine is always available, so the platform stays fully functional
    whether or not a Qwen key is configured.
    """
    key_present = api_key_configured()
    cooling = qwen_cooling_down()

    if not key_present:
        detail = "No Qwen API key is configured, so analyses run on the local engine."
    elif cooling:
        detail = qwen_last_reason() or "Qwen was unavailable on a recent request."
    else:
        detail = "Qwen is configured and will be tried first."

    return {
        "modes": list(ENGINE_MODES),
        "default_mode": default_engine_mode(),
        "api_key_configured": key_present,
        "qwen_available": key_present and not cooling,
        "last_failure_reason": qwen_last_reason(),
        "detail": detail,
    }
