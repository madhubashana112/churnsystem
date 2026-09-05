"""
Keyword-weighted churn scoring for free-text columns.

Support tickets and complaint notes carry intent that no numeric column does — a
customer asking for a porting code or naming a competitor is telling you they
are leaving. This scores that text without a model call, so it works offline and
its output is exactly assertable in tests.
"""
import re
from typing import Dict, Iterable, List, Optional

import pandas as pd

# Weights are intent strength, not sentiment: "cancel" is a stronger churn signal
# than "slow", even though both are negative.
CHURN_LEXICON: Dict[str, float] = {
    # Explicit exit intent
    "cancel": 3.0,
    "terminate": 3.0,
    "close my account": 3.0,
    "port out": 3.0,
    "porting": 3.0,
    "mnp": 3.0,
    "switch": 2.5,
    "leaving": 2.5,
    "competitor": 2.5,
    "cheaper elsewhere": 2.5,
    # Trust damage
    "fraud": 2.5,
    "chargeback": 2.5,
    "dispute": 2.0,
    "unauthorised": 2.5,
    "unauthorized": 2.5,
    "refund": 2.0,
    "overcharged": 2.0,
    # Unresolved friction
    "unresolved": 2.0,
    "escalat": 2.0,
    "still not fixed": 2.0,
    "third time": 2.0,
    "no response": 2.0,
    "useless": 2.0,
    "frustrat": 1.8,
    "disappoint": 1.8,
    # Service quality
    "outage": 1.5,
    "down again": 1.5,
    "keeps dropping": 1.5,
    "dropped": 1.2,
    "slow": 1.5,
    "lag": 1.5,
    "broken": 1.5,
    "error": 1.0,
    "bug": 1.0,
}

# Sorted longest-first so "close my account" is matched before "cancel" style
# overlaps, and each phrase is counted once per row.
_PATTERNS = [
    (re.compile(re.escape(term), re.I), weight)
    for term, weight in sorted(CHURN_LEXICON.items(), key=lambda kv: -len(kv[0]))
]

NEGATIVE_THRESHOLD = 2.0

# Column names worth reading as prose.
_TEXT_COLUMN = re.compile(
    r"(note|notes|comment|description|subject|message|body|reason|feedback|category)", re.I
)


class KeywordSentimentScorer:
    """
    Per-entity churn intent from free text.

    ``text_churn_score`` is the mean weight per text row, so an entity with one
    furious ticket is not out-ranked by an entity with ten mild ones purely on
    volume — volume is already captured by the row-count features.
    """

    def score_text(self, text: str) -> float:
        """Total keyword weight in one string. Each phrase counts once."""
        if not isinstance(text, str) or not text.strip():
            return 0.0
        return sum(weight for pattern, weight in _PATTERNS if pattern.search(text))

    def text_columns(self, df: pd.DataFrame) -> List[str]:
        """Prose-like columns, ignoring ones with a single repeated value."""
        columns = []
        for column in df.columns:
            if not _TEXT_COLUMN.search(str(column)):
                continue
            if pd.api.types.is_numeric_dtype(df[column]):
                continue
            # A column that is the same string on every row carries no
            # information. With a single row there is nothing to compare, so the
            # guard only applies once there is more than one.
            if len(df) > 1 and df[column].nunique(dropna=True) <= 1:
                continue
            columns.append(column)
        return columns

    def score_frame(
        self,
        df: pd.DataFrame,
        join_key: str,
        columns: Optional[Iterable[str]] = None,
    ) -> pd.DataFrame:
        """
        One row per entity: ``text_churn_score`` and ``has_negative_text``.

        Returns an empty frame when there is nothing prose-like to read, so the
        caller simply merges nothing rather than special-casing.
        """
        if join_key not in df.columns:
            return pd.DataFrame()

        selected = list(columns) if columns is not None else self.text_columns(df)
        if not selected:
            return pd.DataFrame()

        combined = df[selected].astype(str).agg(" ".join, axis=1)
        scored = pd.DataFrame({
            join_key: df[join_key],
            "_score": combined.map(self.score_text),
        })

        grouped = scored.groupby(join_key)["_score"]
        out = grouped.mean().round(3).reset_index(name="text_churn_score")
        out["has_negative_text"] = (out["text_churn_score"] >= NEGATIVE_THRESHOLD).astype(int)
        return out
