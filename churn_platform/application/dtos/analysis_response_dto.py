from pydantic import BaseModel
from typing import List
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook
from churn_platform.domain.models.schema_mapping import SchemaMapping

class AnalysisResponse(BaseModel):
    schema_mapping: SchemaMapping
    predictions: List[dict] # combining prediction and playbook
