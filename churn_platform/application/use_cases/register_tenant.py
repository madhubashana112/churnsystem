import uuid
from churn_platform.domain.models.tenant import Tenant
from churn_platform.domain.interfaces.i_repository import ITenantRepository
from churn_platform.application.dtos.tenant_dto import RegisterTenantRequest, TenantResponse

class RegisterTenantUseCase:
    def __init__(self, tenant_repo: ITenantRepository):
        self.tenant_repo = tenant_repo

    async def execute(self, request: RegisterTenantRequest) -> TenantResponse:
        tenant_id = str(uuid.uuid4())
        tenant = Tenant(tenant_id=tenant_id, name=request.name, sector=request.sector)
        await self.tenant_repo.save(tenant)
        
        return TenantResponse(tenant_id=tenant.tenant_id, name=tenant.name, sector=tenant.sector)
