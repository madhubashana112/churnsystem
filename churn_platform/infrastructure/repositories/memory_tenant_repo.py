from typing import Optional
from churn_platform.domain.interfaces.i_repository import ITenantRepository
from churn_platform.domain.models.tenant import Tenant

class MemoryTenantRepository(ITenantRepository):
    def __init__(self):
        self._tenants = {}

    async def save(self, tenant: Tenant) -> None:
        self._tenants[tenant.tenant_id] = tenant

    async def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)
