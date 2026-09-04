from pydantic import BaseModel
from typing import Dict, Any

class CustomerFeatures(BaseModel):
    entity_id: str
    features: Dict[str, Any]
