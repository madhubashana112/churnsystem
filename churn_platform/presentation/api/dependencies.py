import logging
import os
import time
from typing import Optional

from churn_platform.config import get_settings
from churn_platform.infrastructure.repositories.stateless_tenant_repo import (
    StatelessTenantRepository,
    encode_tenant_id,
)
from churn_platform.infrastructure.repositories.memory_analysis_repo import MemoryAnalysisRepository
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.parsers.schema_resolver import AISchemaResolver
from churn_platform.infrastructure.parsers.feature_synthesizer import PandasFeatureSynthesizer
from churn_platform.infrastructure.parsers.sector_feature_enrichers import SectorFeatureEnricher
from churn_platform.infrastructure.ai.cores.saas_core import SaasCore
from churn_platform.infrastructure.ai.cores.telecom_core import TelecomCore
from churn_platform.infrastructure.ai.cores.fintech_core import FintechCore
from churn_platform.infrastructure.local_engine.heuristic_schema_resolver import HeuristicSchemaResolver
from churn_platform.infrastructure.local_engine.local_churn_core import LocalChurnCore

logger = logging.getLogger(__name__)

# Singletons for MVP
# Stateless: works identically on one process or across serverless instances.
_tenant_repo = StatelessTenantRepository()
_analysis_repo = MemoryAnalysisRepository()
_feature_synthesizer = PandasFeatureSynthesizer()
_sector_enricher = SectorFeatureEnricher()

_local_resolver = HeuristicSchemaResolver()
_local_cores = {
    "saas": LocalChurnCore("SaaS"),
    "telecom": LocalChurnCore("Telecom"),
    "fintech": LocalChurnCore("FinTech"),
}

CANONICAL_SECTORS = {"saas": "SaaS", "telecom": "Telecom", "fintech": "FinTech"}
VALID_SECTORS = tuple(CANONICAL_SECTORS.values())

ENGINE_MODES = ("auto", "qwen", "local")


def normalise_sector(sector: str) -> Optional[str]:
    """
    Canonical sector name, or None if unrecognised.

    Accepts any casing and surrounding whitespace: "saas" and " SaaS " both
    resolve, where an exact match would raise on a perfectly valid request.
    """
    return CANONICAL_SECTORS.get((sector or "").strip().lower())


def default_engine_mode() -> str:
    mode = (os.getenv("CHURN_ENGINE") or get_settings().churn_engine or "auto").strip().lower()
    return mode if mode in ENGINE_MODES else "auto"


# After Qwen fails, stop retrying it for a while. Without this every request pays
# the latency of two calls that are already known to fail.
_qwen_unavailable_until = 0.0
_qwen_last_reason: Optional[str] = None


def note_qwen_failure(reason: str) -> None:
    global _qwen_unavailable_until, _qwen_last_reason
    _qwen_unavailable_until = time.monotonic() + get_settings().qwen_cooldown_seconds
    _qwen_last_reason = reason


def note_qwen_success() -> None:
    global _qwen_unavailable_until, _qwen_last_reason
    _qwen_unavailable_until = 0.0
    _qwen_last_reason = None


def qwen_cooling_down() -> bool:
    return time.monotonic() < _qwen_unavailable_until


def qwen_last_reason() -> Optional[str]:
    return _qwen_last_reason


def api_key_configured() -> bool:
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
    return bool(key and key.strip() and key.strip() != "MISSING_KEY")


# The gateway raises without a key, so it is built on first use rather than at
# import: a keyless deployment must still start and serve the local engine.
_qwen_gateway: Optional[QwenGateway] = None
_ai_resolver: Optional[AISchemaResolver] = None
_ai_cores: dict = {}


def get_qwen_gateway() -> QwenGateway:
    global _qwen_gateway
    if _qwen_gateway is None:
        _qwen_gateway = QwenGateway()
    return _qwen_gateway


def get_tenant_repo():
    return _tenant_repo


def get_tenant_id_factory():
    return encode_tenant_id


def get_analysis_repo():
    return _analysis_repo


def get_schema_resolver():
    global _ai_resolver
    if _ai_resolver is None:
        _ai_resolver = AISchemaResolver(get_qwen_gateway())
    return _ai_resolver


def get_local_schema_resolver():
    return _local_resolver


def get_feature_synthesizer():
    return _feature_synthesizer


def get_sector_enricher():
    return _sector_enricher


def get_sector_core(sector: str):
    canonical = normalise_sector(sector)
    if canonical is None:
        raise ValueError(f"Invalid sector: {sector!r}")

    if canonical not in _ai_cores:
        gateway = get_qwen_gateway()
        _ai_cores[canonical] = {
            "SaaS": SaasCore,
            "Telecom": TelecomCore,
            "FinTech": FintechCore,
        }[canonical](gateway)
    return _ai_cores[canonical]


def get_local_sector_core(sector: str):
    canonical = normalise_sector(sector)
    if canonical is None:
        raise ValueError(f"Invalid sector: {sector!r}")
    return _local_cores[canonical.lower()]
