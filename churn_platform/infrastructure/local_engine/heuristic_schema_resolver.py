"""
A schema resolver that needs no model call.

It reads the CSV samples the same way the AI resolver does, but classifies each
table by inspecting column names and cardinality. This keeps the platform fully
functional with no API key, and gives the AI path a deterministic fallback.
"""
import io
import re
from collections import Counter
from typing import Dict, List, Optional

import pandas as pd

from churn_platform.domain.interfaces.i_schema_resolver import ISchemaResolver
from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification

_DATE_NAME = re.compile(r'(date|time|_at$|_ts$|timestamp)', re.I)
_ID_NAME = re.compile(r'_id$|^id$', re.I)
# Columns that identify a device or person rather than describe behaviour.
_NOISE_NAME = re.compile(r'(hash|imsi|mac|ip_address|user_agent|session|device|uuid|guid)', re.I)
_TEXT_NAME = re.compile(r'(note|notes|comment|description|subject|message|body|reason)', re.I)


class HeuristicSchemaResolver(ISchemaResolver):
    async def resolve(self, file_samples: Dict[str, str]) -> SchemaMapping:
        frames = {}
        for name, sample_csv in file_samples.items():
            try:
                frames[name] = pd.read_csv(io.StringIO(sample_csv))
            except Exception:
                continue

        if not frames:
            raise ValueError('No parseable table samples were supplied.')

        primary_key = self._pick_primary_key(frames)
        dimension = self._pick_dimension(frames, primary_key)

        tables: List[TableClassification] = []
        for name, df in frames.items():
            columns = list(df.columns)
            key = primary_key if primary_key in columns else self._first_id(columns) or primary_key

            tables.append(TableClassification(
                file_name=name,
                role=self._role(name, df, is_dimension=(name == dimension)),
                primary_entity_key=key,
                timestamp_column=self._timestamp_column(columns),
                noise_columns=[c for c in columns if _NOISE_NAME.search(str(c))],
            ))

        return SchemaMapping(primary_entity_key=primary_key, tables=tables)

    # ---------------------------------------------------------------- internals

    def _pick_primary_key(self, frames: Dict[str, pd.DataFrame]) -> str:
        """The id-shaped column shared by the most tables is the join key."""
        counts = Counter()
        for df in frames.values():
            for column in df.columns:
                if _ID_NAME.search(str(column)):
                    counts[column] += 1

        if counts:
            # Ties break towards the column appearing in more tables, then by name.
            best = max(counts.items(), key=lambda kv: (kv[1], -len(kv[0])))
            if best[1] >= 2:
                return best[0]
            return best[0]

        first = next(iter(frames.values()))
        return str(first.columns[0])

    def _pick_dimension(self, frames: Dict[str, pd.DataFrame], primary_key: str) -> Optional[str]:
        """The dimension table holds one row per entity — the key is unique in it."""
        candidates = []
        for name, df in frames.items():
            if primary_key not in df.columns:
                continue
            # Samples are only a few rows, so also lean on the file name.
            unique_ratio = df[primary_key].nunique() / max(len(df), 1)
            looks_like_master = bool(re.search(
                r'(user|subscriber|account|customer|client|member)', name, re.I))
            candidates.append((looks_like_master, unique_ratio, -len(df.columns), name))

        if not candidates:
            return None
        return max(candidates)[3]

    def _role(self, name: str, df: pd.DataFrame, is_dimension: bool) -> str:
        if is_dimension:
            return 'DIMENSION'

        columns = [str(c) for c in df.columns]
        if any(_TEXT_NAME.search(c) for c in columns):
            return 'UNSTRUCTURED_TEXT'

        has_amount = any(re.search(r'(amount|price|value|balance|total)', c, re.I) for c in columns)
        if has_amount:
            return 'TRANSACTIONAL'

        if self._timestamp_column(columns):
            return 'TIME_SERIES_EVENT'

        return 'TRANSACTIONAL'

    def _timestamp_column(self, columns) -> Optional[str]:
        for column in columns:
            if _DATE_NAME.search(str(column)):
                return str(column)
        return None

    def _first_id(self, columns) -> Optional[str]:
        for column in columns:
            if _ID_NAME.search(str(column)):
                return str(column)
        return None
