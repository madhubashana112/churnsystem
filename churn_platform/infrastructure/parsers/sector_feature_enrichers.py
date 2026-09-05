"""
Sector-specific feature maths, applied after generic synthesis.

The synthesizer stays sector-agnostic on purpose: it sees a SchemaMapping, not a
vertical. Branching on sector there would push business knowledge into the parser
layer and mean editing two places to add a vertical. Enrichment happens here
instead, dispatched by sector, so both the model path and the local engine get
the same derived signals.
"""
import logging
import re
from typing import Dict, List, Optional

import pandas as pd

from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.schema_mapping import SchemaMapping

logger = logging.getLogger(__name__)

RAPID_DRAIN_THRESHOLD = 0.6


def _slug(value: str) -> str:
    return re.sub(r'[^0-9a-zA-Z]+', '_', str(value)).strip('_').lower()


def _find_table(frames: Dict[str, pd.DataFrame], *keywords: str) -> Optional[str]:
    for name in frames:
        if any(k in name.lower() for k in keywords):
            return name
    return None


def _column(df: pd.DataFrame, pattern: str) -> Optional[str]:
    rx = re.compile(pattern, re.I)
    for column in df.columns:
        if rx.search(str(column)):
            return str(column)
    return None


class SectorFeatureEnricher:
    """Adds per-sector derived features onto already-synthesized entities."""

    def enrich(
        self,
        sector: str,
        features: List[CustomerFeatures],
        schema: SchemaMapping,
        dataframes: Dict[str, pd.DataFrame],
    ) -> List[CustomerFeatures]:
        if not features:
            return features

        key = (sector or "").strip().lower()
        handler = {
            "fintech": self._enrich_fintech,
            "telecom": self._enrich_telecom,
            "saas": self._enrich_saas,
        }.get(key)

        if handler is None:
            return features

        try:
            derived = handler(schema, dataframes)
        except Exception:
            # Enrichment is additive; never let it take down an otherwise good run.
            logger.exception("Sector enrichment failed for %s; continuing without it.", sector)
            return features

        if not derived:
            return features

        for entity in features:
            for name, value in derived.get(entity.entity_id, {}).items():
                entity.features[name] = value
        return features

    # ------------------------------------------------------------- FinTech

    def _enrich_fintech(self, schema, frames) -> Dict[str, Dict[str, float]]:
        """
        Balance drain and P2P reliability.

        The ledger has no running balance and no direction flag on P2P, so P2P is
        treated as balance-neutral: counting inbound P2P as outflow would
        systematically overstate drain. Drain therefore comes from DEPOSIT and
        WITHDRAWAL only, and P2P health is reported separately as a failure streak.
        """
        name = _find_table(frames, "ledger", "transaction")
        if not name:
            return {}

        df = frames[name]
        key = schema.primary_entity_key
        if key not in df.columns:
            return {}

        type_col = _column(df, r"tx_type|type|direction")
        amount_col = _column(df, r"amount|value")
        status_col = _column(df, r"status|state")
        date_col = _column(df, r"date|time|_at$|timestamp")

        out: Dict[str, Dict[str, float]] = {}
        if not (type_col and amount_col):
            return out

        types = df[type_col].astype(str).str.upper()
        amounts = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0)

        work = pd.DataFrame({
            "_key": df[key].astype(str),
            "_type": types,
            "_amount": amounts,
        })
        inflow = work[work["_type"].str.contains("DEPOSIT")].groupby("_key")["_amount"].sum()
        outflow = work[work["_type"].str.contains("WITHDRAW")].groupby("_key")["_amount"].sum()

        for entity in work["_key"].unique():
            i = float(inflow.get(entity, 0.0))
            o = float(outflow.get(entity, 0.0))
            drain = round(o / max(i + o, 1.0), 3)
            out[entity] = {
                "balance_drain_ratio": drain,
                "rapid_balance_drain": int(drain > RAPID_DRAIN_THRESHOLD),
            }

        if status_col:
            streaks = self._p2p_failure_streaks(df, key, type_col, status_col, date_col)
            for entity, streak in streaks.items():
                out.setdefault(entity, {})["p2p_failure_streak"] = streak

        return out

    def _p2p_failure_streaks(self, df, key, type_col, status_col, date_col) -> Dict[str, int]:
        """Longest run of consecutive failed P2P transfers, in time order."""
        p2p = df[df[type_col].astype(str).str.upper().str.contains("P2P")]
        if p2p.empty:
            return {}

        p2p = p2p.copy()
        if date_col:
            p2p["_ts"] = pd.to_datetime(p2p[date_col], errors="coerce", utc=True, format="mixed")
            p2p = p2p.sort_values("_ts")

        failed = p2p[status_col].astype(str).str.upper().str.contains("FAIL")
        p2p = p2p.assign(_failed=failed.values)

        streaks: Dict[str, int] = {}
        for entity, group in p2p.groupby(p2p[key].astype(str), sort=False):
            best = current = 0
            for is_failed in group["_failed"]:
                current = current + 1 if is_failed else 0
                best = max(best, current)
            streaks[entity] = int(best)
        return streaks

    # ------------------------------------------------------------- Telecom

    def _enrich_telecom(self, schema, frames) -> Dict[str, Dict[str, float]]:
        """Top-up cadence: widening gaps between recharges precede a port-out."""
        name = _find_table(frames, "recharge", "topup", "top_up")
        if not name:
            return {}

        df = frames[name]
        key = schema.primary_entity_key
        date_col = _column(df, r"date|time|_at$|timestamp")
        if key not in df.columns or not date_col:
            return {}

        work = pd.DataFrame({
            "_key": df[key].astype(str),
            "_ts": pd.to_datetime(df[date_col], errors="coerce", utc=True, format="mixed"),
        }).dropna(subset=["_ts"]).sort_values("_ts")

        out: Dict[str, Dict[str, float]] = {}
        for entity, group in work.groupby("_key", sort=False):
            stamps = group["_ts"].tolist()
            if len(stamps) < 2:
                out[entity] = {
                    "avg_recharge_gap_days": 0.0,
                    "max_recharge_gap_days": 0.0,
                    "expanding_topup_intervals": 0,
                }
                continue

            gaps = [
                round((stamps[i + 1] - stamps[i]).total_seconds() / 86400, 2)
                for i in range(len(stamps) - 1)
            ]
            # Compare the two most recent gaps with the two earliest: a customer
            # drifting away tops up less and less often.
            half = max(len(gaps) // 2, 1)
            early = sum(gaps[:half]) / half
            late = sum(gaps[-half:]) / half

            out[entity] = {
                "avg_recharge_gap_days": round(sum(gaps) / len(gaps), 2),
                "max_recharge_gap_days": round(max(gaps), 2),
                "expanding_topup_intervals": int(late > early * 1.5 and late > 1.0),
            }
        return out

    # ---------------------------------------------------------------- SaaS

    def _enrich_saas(self, schema, frames) -> Dict[str, Dict[str, float]]:
        """
        Export ratio.

        A spike in exports against total activity reads as a customer taking
        their data with them before they leave.
        """
        name = _find_table(frames, "event", "activity", "usage")
        if not name:
            return {}

        df = frames[name]
        key = schema.primary_entity_key
        type_col = _column(df, r"event_type|action|type|name")
        if key not in df.columns or not type_col:
            return {}

        work = pd.DataFrame({
            "_key": df[key].astype(str),
            "_type": df[type_col].astype(str).str.lower(),
        })
        totals = work.groupby("_key").size()
        exports = work[work["_type"].str.contains("export|download")].groupby("_key").size()

        return {
            entity: {"export_ratio": round(float(exports.get(entity, 0)) / max(int(total), 1), 3)}
            for entity, total in totals.items()
        }
