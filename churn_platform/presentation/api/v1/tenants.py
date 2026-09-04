from fastapi import APIRouter, Depends, HTTPException

from churn_platform.application.dtos.tenant_dto import RegisterTenantRequest, TenantResponse
from churn_platform.application.use_cases.register_tenant import RegisterTenantUseCase
from churn_platform.infrastructure.samples import sample_catalog

router = APIRouter(prefix="/tenants", tags=["Tenants"])

VALID_SECTORS = ["SaaS", "Telecom", "FinTech"]


def get_register_use_case():
    from churn_platform.presentation.api.dependencies import get_tenant_repo
    return RegisterTenantUseCase(get_tenant_repo())


@router.post("/", response_model=TenantResponse)
async def register_tenant(
    request: RegisterTenantRequest,
    use_case: RegisterTenantUseCase = Depends(get_register_use_case),
):
    if request.sector not in VALID_SECTORS:
        raise HTTPException(status_code=400, detail="Invalid sector. Must be SaaS, Telecom, or FinTech")
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Company name cannot be empty")
    return await use_case.execute(request)


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str):
    """
    Lets the dashboard confirm its stored workspace is still live. The repository
    is in-memory, so a server restart invalidates every previously issued id.
    """
    from churn_platform.presentation.api.dependencies import get_tenant_repo

    tenant = await get_tenant_repo().get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "sector": tenant.sector,
        "samples_available": sample_catalog.has_samples(tenant.sector),
    }
