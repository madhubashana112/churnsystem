from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Tenant(BaseModel):
    tenant_id: str
    name: str
    sector: str = Field(description="SaaS, Telecom, or FinTech")
