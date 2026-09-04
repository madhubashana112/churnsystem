from pydantic import BaseModel
from typing import List

class ChurnPrediction(BaseModel):
    entity_id: str
    churn_probability: float
    risk_tier: str
    primary_drivers: List[str] | None = None
    root_cause: str | None = None
    dormancy_type: str | None = None
    regional_network_impact_flag: bool | None = None
