from typing import Dict, List, Optional

import pandas as pd

from churn_platform.domain.interfaces.i_feature_synthesizer import IFeatureSynthesizer
from churn_platform.domain.models.schema_mapping import SchemaMapping
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.infrastructure.parsers.sector_feature_enrichers import SectorFeatureEnricher


class SynthesizeFeaturesUseCase:
    """
    Generic synthesis, then optional sector enrichment.

    Passing a sector enriches the result with vertical-specific maths; omitting
    one yields the sector-agnostic primitives alone.
    """

    def __init__(
        self,
        synthesizer: IFeatureSynthesizer,
        enricher: Optional[SectorFeatureEnricher] = None,
    ):
        self.synthesizer = synthesizer
        self.enricher = enricher or SectorFeatureEnricher()

    def execute(
        self,
        schema: SchemaMapping,
        dataframes: Dict[str, pd.DataFrame],
        sector: Optional[str] = None,
    ) -> List[CustomerFeatures]:
        features = self.synthesizer.synthesize(schema, dataframes)
        if sector:
            features = self.enricher.enrich(sector, features, schema, dataframes)
        return features
