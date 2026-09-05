import logging
from typing import List, Optional, Tuple

from churn_platform.config import get_settings
from churn_platform.domain.interfaces.i_churn_core import IChurnCore
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook

logger = logging.getLogger(__name__)


class ExecuteSectorAnalysisUseCase:
    """
    Scores a cohort in batches.

    Batching lives here rather than in the cores because the three cores are
    near-duplicates; chunking there would triplicate it. Batches run
    sequentially, not via asyncio.gather, to stay within provider rate limits,
    and one failing batch is logged and skipped rather than losing the run.
    """

    def __init__(self, batch_size: Optional[int] = None):
        self.batch_size = batch_size or get_settings().batch_size

    async def execute(
        self, core: IChurnCore, features: List[CustomerFeatures]
    ) -> List[Tuple[ChurnPrediction, RetentionPlaybook]]:
        if not features:
            return []

        size = max(int(self.batch_size), 1)
        if len(features) <= size:
            return await core.analyze(features)

        results: List[Tuple[ChurnPrediction, RetentionPlaybook]] = []
        failed_batches = 0

        for start in range(0, len(features), size):
            batch = features[start:start + size]
            try:
                results.extend(await core.analyze(batch))
            except Exception:
                failed_batches += 1
                logger.exception(
                    "Batch %d-%d failed; continuing with the remaining entities.",
                    start, start + len(batch) - 1,
                )

        if failed_batches and not results:
            raise RuntimeError(f"All {failed_batches} batches failed to score.")
        return results
