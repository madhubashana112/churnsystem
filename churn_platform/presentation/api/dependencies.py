from churn_platform.infrastructure.repositories.memory_tenant_repo import MemoryTenantRepository
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.parsers.schema_resolver import AISchemaResolver
from churn_platform.infrastructure.parsers.feature_synthesizer import PandasFeatureSynthesizer
from churn_platform.infrastructure.ai.cores.saas_core import SaasCore
from churn_platform.infrastructure.ai.cores.telecom_core import TelecomCore
from churn_platform.infrastructure.ai.cores.fintech_core import FintechCore

# Singletons for MVP
_tenant_repo = MemoryTenantRepository()
_qwen_gateway = QwenGateway()
_schema_resolver = AISchemaResolver(_qwen_gateway)
_feature_synthesizer = PandasFeatureSynthesizer()

_saas_core = SaasCore(_qwen_gateway)
_telecom_core = TelecomCore(_qwen_gateway)
_fintech_core = FintechCore(_qwen_gateway)

def get_tenant_repo():
    return _tenant_repo

def get_schema_resolver():
    return _schema_resolver

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
