from pydantic import BaseModel

class RegisterTenantRequest(BaseModel):
    name: str
    sector: str

class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    sector: str
