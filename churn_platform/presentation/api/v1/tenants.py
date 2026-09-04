from fastapi import APIRouter, Depends, HTTPException
from churn_platform.application.dtos.tenant_dto import RegisterTenantRequest, TenantResponse
from churn_platform.application.use_cases.register_tenant import RegisterTenantUseCase

router = APIRouter(prefix="/tenants", tags=["Tenants"])

def get_register_use_case():
    from churn_platform.presentation.api.dependencies import get_tenant_repo
    return RegisterTenantUseCase(get_tenant_repo())

@router.post("/", response_model=TenantResponse)
async def register_tenant(request: RegisterTenantRequest, use_case: RegisterTenantUseCase = Depends(get_register_use_case)):
    if request.sector not in ["SaaS", "Telecom", "FinTech"]:
        raise HTTPException(status_code=400, detail="Invalid sector. Must be SaaS, Telecom, or FinTech")
    return await use_case.execute(request)
