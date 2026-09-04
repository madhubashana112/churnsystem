import pandas as pd
from typing import Dict, List
from churn_platform.domain.interfaces.i_feature_synthesizer import IFeatureSynthesizer
from churn_platform.domain.models.schema_mapping import SchemaMapping
from churn_platform.domain.models.customer_features import CustomerFeatures

class PandasFeatureSynthesizer(IFeatureSynthesizer):
    def synthesize(self, schema: SchemaMapping, dataframes: Dict[str, pd.DataFrame]) -> List[CustomerFeatures]:
        primary_key = schema.primary_entity_key
        
        # Clean noise columns
        for table_meta in schema.tables:
            df = dataframes[table_meta.file_name]
            cols_to_drop = [c for c in table_meta.noise_columns if c in df.columns]
            if cols_to_drop:
                dataframes[table_meta.file_name] = df.drop(columns=cols_to_drop)

        # Merge all on primary key (simplistic approach for MVP)
        # Find the dimension table as base
        base_df = None
        for table_meta in schema.tables:
            if table_meta.role == 'DIMENSION':
                base_df = dataframes[table_meta.file_name]
                break
        
        if base_df is None:
            # Fallback: grab first DF
            base_df = list(dataframes.values())[0]

        # Aggregate other tables
        for table_meta in schema.tables:
            if table_meta.role == 'DIMENSION':
                continue
            
            df = dataframes[table_meta.file_name]
            join_key = table_meta.primary_entity_key
            
            if join_key in df.columns:
                # Basic aggregation (count rows for now, can be expanded to sum, etc)
                agg_df = df.groupby(join_key).size().reset_index(name=f'{table_meta.file_name}_count')
                base_df = pd.merge(base_df, agg_df, left_on=primary_key, right_on=join_key, how='left')
        
        # Convert to CustomerFeatures
        base_df = base_df.fillna(0) # Simple imputation
        features_list = []
        
        for _, row in base_df.iterrows():
            row_dict = row.to_dict()
            entity_id = str(row_dict.pop(primary_key))
            features_list.append(CustomerFeatures(entity_id=entity_id, features=row_dict))
            
        return features_list
