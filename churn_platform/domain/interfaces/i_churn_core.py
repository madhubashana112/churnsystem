from abc import ABC, abstractmethod
from typing import Tuple, List
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook

class IChurnCore(ABC):
    @abstractmethod
    async def analyze(self, features: List[CustomerFeatures]) -> List[Tuple[ChurnPrediction, RetentionPlaybook]]:
        pass
