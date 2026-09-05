import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from churn_platform.domain.interfaces.i_feature_synthesizer import IFeatureSynthesizer
from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.infrastructure.parsers.text_features import KeywordSentimentScorer

logger = logging.getLogger(__name__)

# Keep the per-entity feature dict small: it is serialised into a model prompt.
MAX_NUMERIC_COLS = 3
MAX_CATEGORICAL_COLS = 2
MAX_CATEGORY_VALUES = 6

RECENT_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 30
# Weeks in the 30-day baseline, so velocity compares like with like.
_BASELINE_WEEKS = BASELINE_WINDOW_DAYS / 7.0
# Half an event per week. Without a floor, a customer who was dormant and made
# one call would divide by zero; with it they read as a surge, which is correct.
_VELOCITY_EPSILON = 0.5

_DATE_NAME = re.compile(r'(date|time|_at$|_ts$|timestamp)', re.I)
# Identifier-ish columns carry no behavioural meaning.
_ID_NAME = re.compile(r'(^id$|_id$|_hash$|hash_|imsi|mac|ip_)', re.I)
# Category values that represent a failed outcome.
_FAILURE_VALUE = re.compile(
    r'(?:fail|declin|drop|error|reject|cancel|overdue|late|unpaid|bounce)', re.I)
_KNOWN_SUFFIX = re.compile(r'\.(csv|tsv|xlsx|xlsm|xls|json)$', re.I)
# file_ingestion names workbook sheets "book.xlsx::Sheet1".
_SHEET_SEPARATOR = '::'


class PandasFeatureSynthesizer(IFeatureSynthesizer):
    """
    Flattens related tables into one row per entity.

    Beyond row counts it derives, per child table, recency and rolling 7d/30d
    windows anchored to the data's own latest timestamp, an activity velocity
    comparing the last week against the prior month, a failure rate from
    status-like columns, and a keyword churn score from free text. Those are the
    signals that separate a churning account from a healthy one.

    The reference point is ``max(timestamp)`` across the data, never the wall
    clock: a fixture generated at a frozen date must produce identical features
    whenever the tests happen to run.
    """

    def __init__(self, text_scorer: Optional[KeywordSentimentScorer] = None):
        self.text_scorer = text_scorer or KeywordSentimentScorer()

    def synthesize(self, schema: SchemaMapping, dataframes: Dict[str, pd.DataFrame]) -> List[CustomerFeatures]:
        if not dataframes:
            return []

        primary_key = schema.primary_entity_key

        # Never mutate the caller's dict: the API layer reuses these frames to
        # report per-file row counts after synthesis has run.
        working: Dict[str, pd.DataFrame] = dict(dataframes)

        # The resolver is a language model, so it can name a table that was never
        # supplied. Work only with classifications we actually hold data for.
        tables = [t for t in schema.tables if t.file_name in working]
        for meta in schema.tables:
            if meta.file_name not in working:
                logger.warning("Schema names %r, which was not supplied; skipping it.", meta.file_name)

        for meta in tables:
            df = working[meta.file_name]
            drop = [c for c in meta.noise_columns if c in df.columns]
            if drop:
                working[meta.file_name] = df.drop(columns=drop)

        reference_ts = self._reference_timestamp(tables, working)

        base_df, base_name = self._pick_base(tables, working, primary_key)
        if base_df is None:
            return []

        base_df = base_df.copy()
        if primary_key in base_df.columns:
            base_df = base_df.drop_duplicates(subset=[primary_key])

        count_columns: List[str] = []

        for meta in tables:
            if meta.file_name == base_name:
                continue

            df = working[meta.file_name]
            join_key = meta.primary_entity_key

            if join_key not in df.columns:
                logger.warning(
                    "Table %r has no join key %r; its features are omitted.", meta.file_name, join_key)
                continue
            if primary_key not in base_df.columns:
                logger.warning("Base table lacks the join key %r; cannot merge %r.", primary_key, meta.file_name)
                continue

            agg, agg_counts = self._aggregate(df, join_key, meta, reference_ts)
            if agg is None:
                continue

            count_columns.extend(agg_counts)
            base_df = base_df.merge(agg, left_on=primary_key, right_on=join_key, how='left')
            # A differing join key survives the merge and collides on the next one.
            if join_key != primary_key and join_key in base_df.columns:
                base_df = base_df.drop(columns=[join_key])

        for column in self._date_columns(base_df)[:1]:
            ages = self._days_since(base_df[column], reference_ts)
            if ages is not None:
                base_df[f'days_since_{self._slug(column)}'] = ages
        base_df = base_df.drop(columns=self._date_columns(base_df), errors='ignore')

        # Only counts mean zero when absent. Filling a recency or a rate with 0
        # would claim "seen today" or "never fails" for an entity with no rows.
        present_counts = list(dict.fromkeys(c for c in count_columns if c in base_df.columns))
        if present_counts:
            base_df[present_counts] = base_df[present_counts].fillna(0)

        has_key = primary_key in base_df.columns
        records = base_df.to_dict('records')

        return [
            CustomerFeatures(
                entity_id=str(row.pop(primary_key)) if has_key else f'row-{position + 1}',
                features=self._clean(row),
            )
            for position, row in enumerate(records)
        ]

    # ---------------------------------------------------------------- internals

    def _reference_timestamp(self, tables, frames) -> Optional[pd.Timestamp]:
        """Latest moment anywhere in the data — the anchor all recency uses."""
        latest = None
        for meta in tables:
            df = frames[meta.file_name]
            for column in self._candidate_date_columns(df, meta):
                parsed = self._parse_dates(df[column])
                if parsed is None:
                    continue
                column_max = parsed.max()
                if pd.notna(column_max) and (latest is None or column_max > latest):
                    latest = column_max
        return latest

    def _candidate_date_columns(self, df: pd.DataFrame, meta: TableClassification) -> List[str]:
        if meta.timestamp_column and meta.timestamp_column in df.columns:
            return [meta.timestamp_column]
        return self._date_columns(df)

    def _pick_base(self, tables, frames, primary_key):
        """The dimension table if one was identified, else whatever carries the key."""
        for meta in tables:
            if meta.role == 'DIMENSION' and primary_key in frames[meta.file_name].columns:
                return frames[meta.file_name], meta.file_name

        for name, df in frames.items():
            if primary_key in df.columns:
                return df, name

        first = next(iter(frames.items()), None)
        return (first[1], first[0]) if first else (None, None)

    def _aggregate(
        self,
        df: pd.DataFrame,
        join_key: str,
        meta: TableClassification,
        reference_ts: Optional[pd.Timestamp],
    ) -> Tuple[Optional[pd.DataFrame], List[str]]:
        """One row per entity summarising this child table."""
        label = self._table_label(meta.file_name)
        grouped = df.groupby(join_key)
        count_columns = [f'{label}_count']

        out = grouped.size().reset_index(name=f'{label}_count')

        date_col = None
        candidates = self._candidate_date_columns(df, meta)
        if candidates:
            date_col = candidates[0]

        if date_col and reference_ts is not None:
            ages = self._days_since(df[date_col], reference_ts)
            if ages is not None:
                out = self._merge_time_features(out, df, join_key, ages, label)
                count_columns += [f'{label}_events_7d', f'{label}_events_30d']

        failure = self._failure_rate(df, join_key, label)
        if failure is not None:
            out = out.merge(failure, on=join_key, how='left')

        if meta.role == 'UNSTRUCTURED_TEXT' or self.text_scorer.text_columns(df):
            text = self.text_scorer.score_frame(df, join_key)
            if not text.empty:
                # Namespace them: two text-bearing tables would otherwise collide
                # and pandas would silently suffix them _x / _y.
                text = text.rename(columns={
                    'text_churn_score': f'{label}_text_churn_score',
                    'has_negative_text': f'{label}_has_negative_text',
                })
                count_columns.append(f'{label}_has_negative_text')
                out = out.merge(text, on=join_key, how='left')

        for column in self._numeric_columns(df, join_key)[:MAX_NUMERIC_COLS]:
            stats = grouped[column]
            col = self._slug(column)
            out = out.merge(stats.sum().reset_index(name=f'{label}_{col}_sum'), on=join_key, how='left')
            out = out.merge(stats.mean().round(2).reset_index(name=f'{label}_{col}_avg'), on=join_key, how='left')

        for column in self._categorical_columns(df, join_key)[:MAX_CATEGORICAL_COLS]:
            counts = df.groupby([join_key, df[column].astype(str)]).size().unstack(fill_value=0)
            counts.columns = [f'{label}_{self._slug(column)}_{self._slug(str(c))}' for c in counts.columns]
            count_columns.extend(counts.columns)
            out = out.merge(counts.reset_index(), on=join_key, how='left')

        return out, count_columns

    def _merge_time_features(self, out, df, join_key, ages, label):
        """Recency, rolling windows, and the velocity that compares them."""
        aged = pd.DataFrame({join_key: df[join_key].values, '_age': ages.values})

        recency = aged.groupby(join_key)['_age'].min().round(1).reset_index(name=f'{label}_recency_days')
        out = out.merge(recency, on=join_key, how='left')

        recent = (
            aged[aged['_age'] <= RECENT_WINDOW_DAYS]
            .groupby(join_key).size().reset_index(name=f'{label}_events_7d')
        )
        month = (
            aged[aged['_age'] <= BASELINE_WINDOW_DAYS]
            .groupby(join_key).size().reset_index(name=f'{label}_events_30d')
        )
        out = out.merge(recent, on=join_key, how='left').merge(month, on=join_key, how='left')
        out[f'{label}_events_7d'] = out[f'{label}_events_7d'].fillna(0)
        out[f'{label}_events_30d'] = out[f'{label}_events_30d'].fillna(0)

        # Baseline is the prior month excluding the recent week, per week.
        prior = aged[(aged['_age'] > RECENT_WINDOW_DAYS) & (aged['_age'] <= 37)]
        prior_weekly = prior.groupby(join_key).size().div(_BASELINE_WEEKS)
        baseline = out[join_key].map(prior_weekly).fillna(0.0).clip(lower=_VELOCITY_EPSILON)

        out[f'{label}_activity_velocity'] = (
            out[f'{label}_events_7d'].div(baseline).round(2)
        )
        return out

    def _failure_rate(self, df: pd.DataFrame, join_key: str, label: str) -> Optional[pd.DataFrame]:
        """Share of this entity's rows whose status-like value reads as a failure."""
        for column in df.columns:
            if column == join_key or pd.api.types.is_numeric_dtype(df[column]):
                continue
            if _ID_NAME.search(str(column)) or _DATE_NAME.search(str(column)):
                continue
            values = df[column].astype(str)
            if values.nunique(dropna=True) > MAX_CATEGORY_VALUES:
                continue
            is_failure = values.str.contains(_FAILURE_VALUE)
            if not is_failure.any():
                continue
            rate = (
                pd.DataFrame({join_key: df[join_key], '_f': is_failure.astype(float)})
                .groupby(join_key)['_f'].mean().round(3)
                .reset_index(name=f'{label}_failure_rate')
            )
            return rate
        return None

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

    def _parse_dates(self, series: pd.Series) -> Optional[pd.Series]:
        parsed = pd.to_datetime(series, errors='coerce', utc=True, format='mixed')
        return None if parsed.notna().sum() == 0 else parsed

    def _days_since(self, series: pd.Series, reference: Optional[pd.Timestamp]) -> Optional[pd.Series]:
        """Age in days relative to the data's own latest timestamp."""
        parsed = self._parse_dates(series)
        if parsed is None:
            return None
        anchor = reference if reference is not None else parsed.max()
        return (anchor - parsed).dt.total_seconds().div(86400).round(1)

    def _table_label(self, file_name: str) -> str:
        """
        Feature-name prefix for a table.

        Splitting on the last '.' would turn "book.xlsx::invoices" into "book",
        collapsing every sheet in a workbook onto one prefix and colliding all
        of their features together.
        """
        base, _, sheet = str(file_name).partition(_SHEET_SEPARATOR)
        base = _KNOWN_SUFFIX.sub('', base)
        return self._slug(f'{base}_{sheet}' if sheet else base)

    def _slug(self, value: str) -> str:
        return re.sub(r'[^0-9a-zA-Z]+', '_', str(value)).strip('_').lower()

    def _clean(self, row: dict) -> dict:
        """Plain JSON-serialisable values, rounded so prompts stay compact."""
        cleaned = {}
        for key, value in row.items():
            if isinstance(value, pd.Timestamp):
                continue
            if hasattr(value, 'item'):
                value = value.item()
            if isinstance(value, float):
                value = round(value, 3)
            cleaned[key] = value
        return cleaned
