from abc import ABC, abstractmethod
from churn_platform.domain.models.tenant import Tenant
from typing import Optional

class ITenantRepository(ABC):
    @abstractmethod
    async def save(self, tenant: Tenant) -> None:
        pass

    @abstractmethod
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        pass
