"""
A churn core that scores locally, with no model call.

Rather than hard-coding thresholds for one dataset, it reads the synthesized
feature names, decides what each one means (recency, engagement volume, failure
counts, monetary value), and ranks every entity against the rest of the cohort.
That keeps it domain-adaptive: whatever tables are uploaded, the same reasoning
applies, and each score comes with the drivers that produced it.
"""
import re
from typing import Dict, List, Tuple

from churn_platform.domain.interfaces.i_churn_core import IChurnCore
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.retention_playbook import RetentionPlaybook

# --- feature-name vocabulary -------------------------------------------------
_RECENCY = re.compile(r'days_since_last', re.I)
_VOLUME = re.compile(r'_count$', re.I)
_MONEY = re.compile(r'(amount|balance|price|value|revenue|total|seats)', re.I)
_TENURE = re.compile(r'(tenure|days_since_signup|days_since_created)', re.I)
# Values that read as a bad outcome when they appear as a category count.
_NEGATIVE = re.compile(
    r'(failed|fail|declined|decline|dropped|drop|error|cancel|churn|'
    r'port_out|portout|very_negative|negative|dispute|fraud|open|overdue|late|refund)', re.I)
_POSITIVE = re.compile(r'(paid|success|approved|completed|resolved|closed|active)', re.I)
# Tables that only exist because something went wrong. For these, a HIGH row count
# is the risk signal — the opposite of an engagement table like events or calls.
_NEGATIVE_TABLE = re.compile(r'(complaint|ticket|dispute|incident|escalation|chargeback|refund)', re.I)

TIER_BOUNDS = [(0.80, 'CRITICAL'), (0.60, 'HIGH'), (0.35, 'MEDIUM')]


def _percentile_ranks(values: List[float]) -> List[float]:
    """
    Rank each value inside the cohort on 0..1. Ties share the average rank, and a
    cohort with no spread collapses to a neutral 0.5 rather than dividing by zero.
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1 or len(set(values)) == 1:
        return [0.5] * n

    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 / (n - 1)
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


class LocalChurnCore(IChurnCore):
    """Deterministic, explainable scoring. `sector` shapes the wording and playbooks."""

    def __init__(self, sector: str):
        self.sector = sector

    async def analyze(
        self, features: List[CustomerFeatures]
    ) -> List[Tuple[ChurnPrediction, RetentionPlaybook]]:
        if not features:
            return []

        signals = self._build_signals(features)
        results = []

        for index, entity in enumerate(features):
            contributions = [(name, weight, scores[index])
                             for name, weight, scores in signals]
            probability = self._blend(contributions)
            tier = self._tier(probability)
            drivers = self._drivers(contributions, entity)

            results.append((
                self._prediction(entity.entity_id, probability, tier, drivers),
                self._playbook(tier, drivers),
            ))

        return results

    # ------------------------------------------------------------- signals

    def _build_signals(self, features: List[CustomerFeatures]):
        """
        Returns [(label, weight, per-entity 0..1 risk scores)]. Each raw feature is
        ranked across the cohort, then flipped so that 1.0 always means "worse".
        """
        keys = sorted({k for f in features for k in f.features})
        signals = []

        def column(key):
            out = []
            for f in features:
                value = f.features.get(key, 0)
                out.append(float(value) if isinstance(value, (int, float)) else 0.0)
            return out

        # Engagement volume: more is better. Grievance volume is handled as a
        # negative signal instead, so that "few complaints" never reads as risk.
        volume_keys = [
            k for k in keys
            if _VOLUME.search(k) and not _NEGATIVE.search(k) and not _NEGATIVE_TABLE.search(k)
        ]

        for key in keys:
            values = column(key)
            if all(v == 0 for v in values):
                continue

            ranks = _percentile_ranks(values)

            if _RECENCY.search(key):
                # A long gap since the last grievance is a good sign, not a bad one.
                if _NEGATIVE_TABLE.search(key):
                    continue
                # Longer since last seen = higher risk.
                signals.append((self._label(key, 'inactivity'), 2.2, ranks))

            elif _NEGATIVE_TABLE.search(key) and _VOLUME.search(key):
                # More complaints / tickets / disputes = higher risk.
                signals.append((self._label(key, 'grievance'), 1.8, ranks))

            elif _NEGATIVE.search(key):
                # More failures = higher risk.
                signals.append((self._label(key, 'negative'), 1.6, ranks))

            elif key in volume_keys:
                # Less activity = higher risk.
                signals.append((self._label(key, 'volume'), 1.4, [1 - r for r in ranks]))

            elif _MONEY.search(key):
                signals.append((self._label(key, 'money'), 1.0, [1 - r for r in ranks]))

            elif _TENURE.search(key):
                # Newer accounts are slightly likelier to leave.
                signals.append((self._label(key, 'tenure'), 0.5, [1 - r for r in ranks]))

            elif _POSITIVE.search(key):
                signals.append((self._label(key, 'positive'), 0.6, [1 - r for r in ranks]))

        if not signals:
            # Nothing interpretable — fall back to a flat neutral cohort.
            signals.append(('insufficient signal in the supplied tables', 1.0,
                            [0.5] * len(features)))
        return signals

    def _blend(self, contributions) -> float:
        total_weight = sum(w for _, w, _ in contributions) or 1.0
        weighted = sum(w * s for _, w, s in contributions) / total_weight

        # Spread the middle of the distribution out so tiers are not all MEDIUM.
        stretched = 0.5 + (weighted - 0.5) * 1.9
        return round(min(max(stretched, 0.01), 0.99), 3)

    def _tier(self, probability: float) -> str:
        for bound, tier in TIER_BOUNDS:
            if probability >= bound:
                return tier
        return 'LOW'

    def _drivers(self, contributions, entity: CustomerFeatures) -> List[str]:
        """The strongest three contributors, phrased for a human."""
        ranked = sorted(contributions, key=lambda c: c[1] * c[2], reverse=True)
        out = []
        for label, _weight, score in ranked:
            if score < 0.55:
                continue
            out.append(f'{label} ({self._severity(score)})')
            if len(out) == 3:
                break
        return out or ['No individual metric stands out; risk comes from the overall profile']

    def _severity(self, score: float) -> str:
        # Phrased in terms of risk rank, so it reads correctly whether the
        # underlying metric is one where high is bad or low is bad.
        if score >= 0.85:
            return 'worst decile in the cohort'
        if score >= 0.7:
            return 'worse than most of the cohort'
        return 'slightly worse than the cohort average'

    def _label(self, key: str, kind: str) -> str:
        """Turn a synthesized feature name into readable English."""
        words = key.replace('_', ' ').strip()

        if kind == 'inactivity':
            subject = re.sub(r'\s*days since last\s*', '', words).strip() or 'activity'
            return f'Long gap since the last {subject} record'
        if kind == 'volume':
            subject = re.sub(r'\s*count\s*$', '', words).strip() or 'activity'
            return f'Low {subject} volume'
        if kind == 'grievance':
            subject = re.sub(r'\s*count\s*$', '', words).strip() or 'grievances'
            return f'High {subject} volume'
        if kind == 'negative':
            return f'Elevated {words}'
        if kind == 'money':
            return f'Low {words}'
        if kind == 'tenure':
            return f'Short {words}'
        return f'Weak {words}'

    # ------------------------------------------------------- sector outputs

    def _prediction(self, entity_id, probability, tier, drivers) -> ChurnPrediction:
        prediction = ChurnPrediction(
            entity_id=entity_id,
            churn_probability=probability,
            risk_tier=tier,
        )

        # Match the field each sector core populates, so the UI reads the same.
        if self.sector == 'Telecom':
            prediction.root_cause = drivers[0]
            prediction.regional_network_impact_flag = any(
                re.search(r'(dropped|network|tower)', d, re.I) for d in drivers)
        elif self.sector == 'FinTech':
            prediction.dormancy_type = self._dormancy_type(probability, drivers)
            prediction.primary_drivers = drivers
        else:
            prediction.primary_drivers = drivers

        return prediction

    def _dormancy_type(self, probability: float, drivers: List[str]) -> str:
        inactive = any(re.search(r'gap since', d, re.I) for d in drivers)
        if probability >= 0.8 and inactive:
            return 'FULL_DORMANCY'
        if inactive:
            return 'PASSIVE_DORMANCY'
        if any(re.search(r'(declined|dispute|failed)', d, re.I) for d in drivers):
            return 'FRICTION_DRIVEN'
        return 'PARTIAL_DORMANCY'

    PLAYBOOKS: Dict[str, Dict[str, Dict[str, str]]] = {
        'SaaS': {
            'CRITICAL': {'action_type': 'CSM_CALL', 'channel': 'PHONE',
                         'payload': 'Book a 15-minute call with the account owner today. Lead with the '
                                    'unresolved tickets, then offer a two-month credit to keep the renewal alive.'},
            'HIGH': {'action_type': 'DISCOUNT', 'channel': 'EMAIL',
                     'payload': 'Send the 20% loyalty renewal offer, and include the onboarding guide for '
                                'the features this account has never activated.'},
            'MEDIUM': {'action_type': 'IN_APP_TOUR', 'channel': 'IN_APP',
                       'payload': 'Trigger the re-engagement tour on next login, highlighting the reporting '
                                  'and export features this workspace has not used yet.'},
            'LOW': {'action_type': 'MONITOR', 'channel': 'IN_APP',
                    'payload': 'Healthy account. Keep in the standard lifecycle nurture and re-check next cycle.'},
        },
        'Telecom': {
            'CRITICAL': {'action_type': 'WIN_BACK_OFFER', 'channel': 'PHONE',
                         'payload': 'Retention desk callback within 24 hours. Authorise the port-out save offer: '
                                    'one month free plus a tariff upgrade at the current price.'},
            'HIGH': {'action_type': 'FREE_DATA', 'channel': 'SMS',
                     'payload': 'Send 10GB of free data valid for 30 days, plus an apology credit for the '
                                'dropped calls logged on this line. Reply YES to activate.'},
            'MEDIUM': {'action_type': 'TARIFF_UPGRADE', 'channel': 'SMS',
                       'payload': 'Offer the higher-value bundle at the current monthly price for three months.'},
            'LOW': {'action_type': 'MONITOR', 'channel': 'USSD',
                    'payload': 'Stable line. No intervention needed; include in the quarterly loyalty campaign.'},
        },
        'FinTech': {
            'CRITICAL': {'action_type': 'FEE_WAIVER', 'channel': 'PHONE',
                         'payload': 'Relationship manager call. Waive this quarter\'s account fees and fast-track '
                                    'the open disputes before the balance is withdrawn.'},
            'HIGH': {'action_type': 'CASHBACK', 'channel': 'PUSH_NOTIFICATION',
                     'payload': 'Offer 5% cashback on the next five card transactions to restart spending, and '
                                'resolve the declined-payment issue on file.'},
            'MEDIUM': {'action_type': 'REACTIVATION_NUDGE', 'channel': 'EMAIL',
                       'payload': 'Send the dormant-account nudge with a reminder of the saving-pot and '
                                  'round-up features attached to this tier.'},
            'LOW': {'action_type': 'MONITOR', 'channel': 'PUSH_NOTIFICATION',
                    'payload': 'Active account. Continue standard engagement messaging.'},
        },
    }

    def _playbook(self, tier: str, drivers: List[str]) -> RetentionPlaybook:
        sector_book = self.PLAYBOOKS.get(self.sector, self.PLAYBOOKS['SaaS'])
        entry = sector_book.get(tier, sector_book['MEDIUM'])
        reason = drivers[0].split(' (')[0].lower() if drivers else 'the overall risk profile'
        return RetentionPlaybook(
            action_type=entry['action_type'],
            channel=entry['channel'],
            action_payload=f"{entry['payload']} Trigger: {reason}.",
        )
