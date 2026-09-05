from fastapi import APIRouter, Depends, HTTPException

from churn_platform.application.dtos.tenant_dto import RegisterTenantRequest, TenantResponse
from churn_platform.application.use_cases.register_tenant import RegisterTenantUseCase
from churn_platform.infrastructure.samples import sample_catalog

router = APIRouter(prefix="/tenants", tags=["Tenants"])

from churn_platform.presentation.api.dependencies import VALID_SECTORS, normalise_sector


def get_register_use_case():
    from churn_platform.presentation.api.dependencies import get_tenant_repo, get_tenant_id_factory
    return RegisterTenantUseCase(get_tenant_repo(), get_tenant_id_factory())


@router.post("/", response_model=TenantResponse)
async def register_tenant(
    request: RegisterTenantRequest,
    use_case: RegisterTenantUseCase = Depends(get_register_use_case),
):
    # Accept any casing: "saas" is a perfectly valid thing for a client to send.
    canonical = normalise_sector(request.sector)
    if canonical is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sector. Must be one of {', '.join(VALID_SECTORS)}.",
        )
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Company name cannot be empty")

    request.sector = canonical
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
