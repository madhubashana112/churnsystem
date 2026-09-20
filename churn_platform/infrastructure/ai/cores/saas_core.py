from typing import List, Tuple

from churn_platform.domain.interfaces.i_churn_core import IChurnCore
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.ai.cores.response_parsing import (
    build_user_prompt,
    parse_predictions,
)
from churn_platform.infrastructure.ai.prompts.saas_prompts import SAAS_CORE_SYSTEM_PROMPT

# Beyond the shared prediction shape, SaaS accounts carry the ranked reasons.
SECTOR_FIELDS = ("primary_drivers",)


class SaasCore(IChurnCore):
    def __init__(self, gateway: QwenGateway):
        self.gateway = gateway

    async def analyze(
        self, features: List[CustomerFeatures]
    ) -> List[Tuple[ChurnPrediction, RetentionPlaybook]]:
        # The cohort arrives already chunked: batching is the use case's job,
        # so that it is not written out once per sector core.
        response = await self.gateway.generate_json(
            SAAS_CORE_SYSTEM_PROMPT, build_user_prompt(features)
        )
        return parse_predictions(response, features, SECTOR_FIELDS)
