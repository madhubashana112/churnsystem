from typing import Optional, Dict

from churn_platform.domain.interfaces.i_analysis_repository import IAnalysisRepository
from churn_platform.domain.models.analysis_snapshot import AnalysisSnapshot


class MemoryAnalysisRepository(IAnalysisRepository):
    """In-memory store, matching the MVP posture of MemoryTenantRepository."""

    def __init__(self):
        self._latest: Dict[str, AnalysisSnapshot] = {}

    async def save(self, snapshot: AnalysisSnapshot) -> None:
        self._latest[snapshot.tenant_id] = snapshot

    async def get_latest(self, tenant_id: str) -> Optional[AnalysisSnapshot]:
        return self._latest.get(tenant_id)
