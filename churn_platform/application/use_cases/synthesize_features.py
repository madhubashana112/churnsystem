import pandas as pd
from typing import Dict, List
from churn_platform.domain.interfaces.i_feature_synthesizer import IFeatureSynthesizer
from churn_platform.domain.models.schema_mapping import SchemaMapping
from churn_platform.domain.models.customer_features import CustomerFeatures

class SynthesizeFeaturesUseCase:
    def __init__(self, synthesizer: IFeatureSynthesizer):
        self.synthesizer = synthesizer

    def execute(self, schema: SchemaMapping, dataframes: Dict[str, pd.DataFrame]) -> List[CustomerFeatures]:
        return self.synthesizer.synthesize(schema, dataframes)
