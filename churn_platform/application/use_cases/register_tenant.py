import uuid
from typing import Callable, Optional

from churn_platform.domain.models.tenant import Tenant
from churn_platform.domain.interfaces.i_repository import ITenantRepository
from churn_platform.application.dtos.tenant_dto import RegisterTenantRequest, TenantResponse


class RegisterTenantUseCase:
    def __init__(
        self,
        tenant_repo: ITenantRepository,
        id_factory: Optional[Callable[[str, str], str]] = None,
    ):
        self.tenant_repo = tenant_repo
        # A stateless repository derives the id from the tenant itself; a storing
        # repository is happy with a random one.
        self.id_factory = id_factory or (lambda name, sector: str(uuid.uuid4()))

    async def execute(self, request: RegisterTenantRequest) -> TenantResponse:
        tenant_id = self.id_factory(request.name, request.sector)
        tenant = Tenant(tenant_id=tenant_id, name=request.name, sector=request.sector)
        await self.tenant_repo.save(tenant)

        return TenantResponse(tenant_id=tenant.tenant_id, name=tenant.name, sector=tenant.sector)
