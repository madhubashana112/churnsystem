from abc import ABC, abstractmethod
from typing import Optional

from churn_platform.domain.models.analysis_snapshot import AnalysisSnapshot


class IAnalysisRepository(ABC):
    """Stores the most recent analysis run for each tenant."""

    @abstractmethod
    async def save(self, snapshot: AnalysisSnapshot) -> None:
        pass

    @abstractmethod
    async def get_latest(self, tenant_id: str) -> Optional[AnalysisSnapshot]:
        pass
