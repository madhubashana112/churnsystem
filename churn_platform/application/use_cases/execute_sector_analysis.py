from typing import List, Tuple
from churn_platform.domain.interfaces.i_churn_core import IChurnCore
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook

class ExecuteSectorAnalysisUseCase:
    async def execute(self, core: IChurnCore, features: List[CustomerFeatures]) -> List[Tuple[ChurnPrediction, RetentionPlaybook]]:
        return await core.analyze(features)
