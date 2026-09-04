import re
from typing import Dict, List, Optional

import pandas as pd

from churn_platform.domain.interfaces.i_feature_synthesizer import IFeatureSynthesizer
from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification
from churn_platform.domain.models.customer_features import CustomerFeatures

# Keep the per-entity feature dict small: it is serialised into a model prompt.
MAX_NUMERIC_COLS = 3
MAX_CATEGORICAL_COLS = 2
MAX_CATEGORY_VALUES = 6

_DATE_NAME = re.compile(r'(date|time|_at$|_ts$|timestamp)', re.I)
# Identifier-ish numeric columns carry no behavioural meaning.
_ID_NAME = re.compile(r'(^id$|_id$|_hash$|hash_|imsi|mac|ip_)', re.I)


class PandasFeatureSynthesizer(IFeatureSynthesizer):
    """
    Flattens a set of related tables into one row per entity.

    Beyond a plain row count it derives, per child table, recency from any date
    column, sums and means of the meaningful numeric columns, and counts per value
    for low-cardinality categoricals. Those are the signals that actually separate
    a churning account from a healthy one.
    """

    def synthesize(self, schema: SchemaMapping, dataframes: Dict[str, pd.DataFrame]) -> List[CustomerFeatures]:
        if not dataframes:
            return []

        primary_key = schema.primary_entity_key

        # The resolver is a language model, so it can name a table that was never
        # supplied. Work only with classifications we actually hold data for.
        tables = [t for t in schema.tables if t.file_name in dataframes]

        for table_meta in tables:
            df = dataframes[table_meta.file_name]
            cols_to_drop = [c for c in table_meta.noise_columns if c in df.columns]
            if cols_to_drop:
                dataframes[table_meta.file_name] = df.drop(columns=cols_to_drop)

        base_df, base_name = self._pick_base(tables, dataframes, primary_key)
        if base_df is None:
            return []

        base_df = base_df.copy()
        if primary_key in base_df.columns:
            base_df = base_df.drop_duplicates(subset=[primary_key])

        for table_meta in tables:
            if table_meta.file_name == base_name:
                continue

            df = dataframes[table_meta.file_name]
            join_key = table_meta.primary_entity_key

            if join_key not in df.columns or primary_key not in base_df.columns:
                continue

            agg = self._aggregate(df, join_key, table_meta)
            if agg is not None:
                base_df = base_df.merge(agg, left_on=primary_key, right_on=join_key, how='left')
                if join_key != primary_key and join_key in base_df.columns:
                    base_df = base_df.drop(columns=[join_key])

        # Recency on the base table itself (e.g. signup / created_at).
        for column in self._date_columns(base_df)[:1]:
            ages = self._days_since(base_df[column])
            if ages is not None:
                base_df[f'days_since_{self._slug(column)}'] = ages
        base_df = base_df.drop(columns=self._date_columns(base_df), errors='ignore')

        base_df = base_df.fillna(0)

        has_key = primary_key in base_df.columns
        features_list: List[CustomerFeatures] = []

        for position, (_, row) in enumerate(base_df.iterrows()):
            row_dict = row.to_dict()
            entity_id = str(row_dict.pop(primary_key)) if has_key else f'row-{position + 1}'
            features_list.append(CustomerFeatures(
                entity_id=entity_id,
                features=self._clean(row_dict),
            ))

        return features_list

    # ---------------------------------------------------------------- internals

    def _pick_base(self, tables, dataframes, primary_key):
        """The dimension table if one was identified, else whatever carries the key."""
        for table_meta in tables:
            if table_meta.role == 'DIMENSION' and primary_key in dataframes[table_meta.file_name].columns:
                return dataframes[table_meta.file_name], table_meta.file_name

        for name, df in dataframes.items():
            if primary_key in df.columns:
                return df, name

        first = next(iter(dataframes.items()), None)
        return (first[1], first[0]) if first else (None, None)

    def _aggregate(self, df: pd.DataFrame, join_key: str, meta: TableClassification) -> Optional[pd.DataFrame]:
        """One row per entity summarising this child table."""
        label = self._slug(meta.file_name.rsplit('.', 1)[0])
        grouped = df.groupby(join_key)

        out = grouped.size().reset_index(name=f'{label}_count')

        # Recency — the single strongest churn signal in most of these tables.
        date_col = meta.timestamp_column if meta.timestamp_column in df.columns else None
        if date_col is None:
            candidates = self._date_columns(df)
            date_col = candidates[0] if candidates else None

        if date_col:
            ages = self._days_since(df[date_col])
            if ages is not None:
                recency = df[[join_key]].assign(_age=ages).groupby(join_key)['_age']
                out = out.merge(
                    recency.min().reset_index(name=f'{label}_days_since_last'), on=join_key, how='left')
                out = out.merge(
                    recency.max().reset_index(name=f'{label}_days_since_first'), on=join_key, how='left')

        for column in self._numeric_columns(df, join_key)[:MAX_NUMERIC_COLS]:
            stats = grouped[column]
            col = self._slug(column)
            out = out.merge(stats.sum().reset_index(name=f'{label}_{col}_sum'), on=join_key, how='left')
            out = out.merge(stats.mean().round(2).reset_index(name=f'{label}_{col}_avg'), on=join_key, how='left')

        for column in self._categorical_columns(df, join_key)[:MAX_CATEGORICAL_COLS]:
            counts = (
                df.groupby([join_key, df[column].astype(str)]).size()
                .unstack(fill_value=0)
            )
            counts.columns = [f'{label}_{self._slug(column)}_{self._slug(str(c))}' for c in counts.columns]
            out = out.merge(counts.reset_index(), on=join_key, how='left')

        return out

    def _numeric_columns(self, df: pd.DataFrame, join_key: str) -> List[str]:
        return [
            c for c in df.columns
            if c != join_key
            and pd.api.types.is_numeric_dtype(df[c])
            and not _ID_NAME.search(str(c))
        ]

    def _categorical_columns(self, df: pd.DataFrame, join_key: str) -> List[str]:
        out = []
        for c in df.columns:
            if c == join_key or pd.api.types.is_numeric_dtype(df[c]):
                continue
            if _ID_NAME.search(str(c)) or _DATE_NAME.search(str(c)):
                continue
            unique = df[c].nunique(dropna=True)
            if 1 < unique <= MAX_CATEGORY_VALUES:
                out.append(c)
        return out

    def _date_columns(self, df: pd.DataFrame) -> List[str]:
        return [c for c in df.columns if _DATE_NAME.search(str(c))]

    def _days_since(self, series: pd.Series) -> Optional[pd.Series]:
        """Age in whole days, or None if the column will not parse as dates."""
        parsed = pd.to_datetime(series, errors='coerce', utc=True, format='mixed')
        if parsed.notna().sum() == 0:
            return None
        now = pd.Timestamp.now(tz='UTC')
        return (now - parsed).dt.total_seconds().div(86400).round(1)

    def _slug(self, value: str) -> str:
        return re.sub(r'[^0-9a-zA-Z]+', '_', str(value)).strip('_').lower()

    def _clean(self, row: dict) -> dict:
        """Plain JSON-serialisable values, rounded so prompts stay compact."""
        cleaned = {}
        for key, value in row.items():
            if isinstance(value, (pd.Timestamp,)):
                continue
            if hasattr(value, 'item'):
                value = value.item()
            if isinstance(value, float):
                value = round(value, 2)
            cleaned[key] = value
        return cleaned
