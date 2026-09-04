import os
import time

from churn_platform.infrastructure.repositories.stateless_tenant_repo import (
    StatelessTenantRepository,
    encode_tenant_id,
)
from churn_platform.infrastructure.repositories.memory_analysis_repo import MemoryAnalysisRepository
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.parsers.schema_resolver import AISchemaResolver
from churn_platform.infrastructure.parsers.feature_synthesizer import PandasFeatureSynthesizer
from churn_platform.infrastructure.ai.cores.saas_core import SaasCore
from churn_platform.infrastructure.ai.cores.telecom_core import TelecomCore
from churn_platform.infrastructure.ai.cores.fintech_core import FintechCore
from churn_platform.infrastructure.local_engine.heuristic_schema_resolver import HeuristicSchemaResolver
from churn_platform.infrastructure.local_engine.local_churn_core import LocalChurnCore

# Singletons for MVP
# Stateless: works identically on one process or across serverless instances.
_tenant_repo = StatelessTenantRepository()
_analysis_repo = MemoryAnalysisRepository()
_qwen_gateway = QwenGateway()
_schema_resolver = AISchemaResolver(_qwen_gateway)
_feature_synthesizer = PandasFeatureSynthesizer()

_saas_core = SaasCore(_qwen_gateway)
_telecom_core = TelecomCore(_qwen_gateway)
_fintech_core = FintechCore(_qwen_gateway)

_local_resolver = HeuristicSchemaResolver()
_local_cores = {
    "SaaS": LocalChurnCore("SaaS"),
    "Telecom": LocalChurnCore("Telecom"),
    "FinTech": LocalChurnCore("FinTech"),
}

VALID_SECTORS = ("SaaS", "Telecom", "FinTech")

# auto  — try Qwen, fall back to the local engine if it is unavailable (default)
# qwen  — Qwen only; surface the error instead of falling back
# local — never call the model
ENGINE_MODES = ("auto", "qwen", "local")


def default_engine_mode() -> str:
    mode = (os.getenv("CHURN_ENGINE") or "auto").strip().lower()
    return mode if mode in ENGINE_MODES else "auto"


# After Qwen fails, stop retrying it for a while. Without this every request pays
# the latency of two calls that are already known to fail.
_QWEN_COOLDOWN_SECONDS = 120
_qwen_unavailable_until = 0.0
_qwen_last_reason = None


def note_qwen_failure(reason: str) -> None:
    global _qwen_unavailable_until, _qwen_last_reason
    _qwen_unavailable_until = time.monotonic() + _QWEN_COOLDOWN_SECONDS
    _qwen_last_reason = reason


def note_qwen_success() -> None:
    global _qwen_unavailable_until, _qwen_last_reason
    _qwen_unavailable_until = 0.0
    _qwen_last_reason = None


def qwen_cooling_down() -> bool:
    return time.monotonic() < _qwen_unavailable_until


def qwen_last_reason():
    return _qwen_last_reason


def api_key_configured() -> bool:
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
    return bool(key and key.strip() and key.strip() != "MISSING_KEY")


def get_tenant_repo():
    return _tenant_repo


def get_tenant_id_factory():
    return encode_tenant_id


def get_analysis_repo():
    return _analysis_repo


def get_schema_resolver():
    return _schema_resolver


def get_local_schema_resolver():
    return _local_resolver


def get_feature_synthesizer():
    return _feature_synthesizer


def get_sector_core(sector: str):
    if sector == "SaaS":
        return _saas_core
    elif sector == "Telecom":
        return _telecom_core
    elif sector == "FinTech":
        return _fintech_core
    raise ValueError("Invalid sector")


def get_local_sector_core(sector: str):
    core = _local_cores.get(sector)
    if core is None:
        raise ValueError("Invalid sector")
    return core
