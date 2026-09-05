"""
Generates the mock datasets under data/.

Two properties matter more than realism here:

1. **Signal.** Each entity is assigned a cohort first and its behaviour is
   generated conditionally, so at-risk entities really do go quiet, complain
   more, fail payments and drift towards competitors. Uniform noise would make
   any feature computed from it meaningless.
2. **Reproducibility.** Every date is an offset from a frozen REFERENCE_DATE and
   every draw is seeded, so two runs are byte-identical and tests can assert on
   exact values. Feature code anchors recency to max(timestamp) rather than the
   wall clock, so frozen data stays meaningful however long after generation it
   is read.

Entities 0-24 are the churning cohort and 25-99 are healthy. That split is
deterministic so tests can assert cohort separation by index.
"""
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SECTOR_DIRS = ['data/saas', 'data/telecom', 'data/fintech']
ENTITY_COUNT = 100
CHURN_COHORT_SIZE = 25
SEED = 42

# Frozen anchor. All timestamps are offsets back from here.
REFERENCE_DATE = datetime(2025, 6, 1, 12, 0, 0)


def create_dirs():
    for d in SECTOR_DIRS:
        os.makedirs(d, exist_ok=True)


def days_before(n) -> datetime:
    return REFERENCE_DATE - timedelta(days=float(n))


def risk_profile(rng, count: int) -> np.ndarray:
    """
    Latent 0..1 churn risk. Indices below CHURN_COHORT_SIZE are the churning
    cohort; the rest are graded healthy so the tier spread stays realistic.
    """
    risk = np.empty(count)
    risk[:CHURN_COHORT_SIZE] = rng.uniform(0.62, 0.97, CHURN_COHORT_SIZE)
    risk[CHURN_COHORT_SIZE:] = rng.uniform(0.02, 0.55, count - CHURN_COHORT_SIZE)
    return np.round(risk, 3)


# --------------------------------------------------------------- text pools
# Churning text carries exit intent; routine text does not. The scorer's lexicon
# keys off these phrasings.
SAAS_CHURN_SUBJECTS = [
    "Cancel subscription at the end of this term",
    "How do I close my account and export everything",
    "Competitor is cheaper for the same seats",
    "Requesting refund for the last two invoices",
    "We are switching to another vendor next month",
    "Third time reporting this and still not fixed",
    "No response on my escalated ticket for a week",
    "Reports are unusable, exports keep failing",
    "Overcharged again on this month's invoice",
    "Very disappointed, considering alternatives",
]
SAAS_ROUTINE_SUBJECTS = [
    "How do I invite a teammate",
    "Question about the reporting filters",
    "Cannot login from the mobile app",
    "Export formatting question",
    "Slow dashboard load in the mornings",
    "Where do I change the billing address",
    "Request for an extra seat",
    "Minor bug in the date picker",
    "How do I set up SSO",
    "Feature request: scheduled reports",
]

TELECOM_CHURN_NOTES = [
    "Asked for the porting authorisation code",
    "Wants to port out to another network",
    "Competitor offered a cheaper bundle, considering MNP",
    "Third complaint about dropped calls, still unresolved",
    "Threatening to cancel the connection this week",
    "Escalated: no response on the previous complaint",
    "Disputes the bill, says overcharged for data",
    "Signal keeps dropping at the home address",
]
TELECOM_ROUTINE_NOTES = [
    "General enquiry about the current plan",
    "Asked about data rollover rules",
    "Requested an itemised bill copy",
    "Query on international roaming rates",
    "Wants to change the billing date",
    "Asked how to check the remaining balance",
    "Enquiry about upgrading the handset",
]


# ----------------------------------------------------------------------- SaaS
def generate_saas_data():
    rng = np.random.default_rng(SEED)
    user_ids = [f'usr_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    users = pd.DataFrame({
        'user_id': user_ids,
        'signup_date': [days_before(rng.integers(30, 700) * (1 - 0.4 * r)).strftime('%Y-%m-%d')
                        for r in risk],
        'seats': [max(1, int(rng.integers(1, 40) * (1 - 0.6 * r))) for r in risk],
        'tier': [rng.choice(['Basic', 'Pro', 'Enterprise'], p=_norm([0.25 + 0.4 * r, 0.45 - 0.15 * r, 0.30 - 0.25 * r]))
                 for r in risk],
        'ip_address': [f'192.168.1.{rng.integers(1, 255)}' for _ in range(ENTITY_COUNT)],
        'last_user_agent': ['Mozilla/5.0'] * ENTITY_COUNT,
    })
    users.to_csv('data/saas/users.csv', index=False)

    # Churning users front-load their activity into the distant past and go quiet,
    # while over-using export just before they leave.
    rows, counter = [], 1
    for uid, r in zip(user_ids, risk):
        volume = int(np.clip(rng.normal(40 * (1 - r) + 4, 6), 2, 120))
        silence = int(rng.integers(0, 4) + r * rng.integers(12, 55))
        export_p = 0.10 + 0.30 * r
        for _ in range(volume):
            age = min(silence + rng.exponential(12 * (1 - 0.5 * r)), 180)
            rows.append({
                'event_id': f'evt_{counter}',
                'user_id': uid,
                'timestamp': days_before(age).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'event_type': rng.choice(
                    ['login', 'feature_a', 'feature_b', 'export', 'logout'],
                    p=_norm([0.40 - 0.15 * r, 0.20 - 0.05 * r, 0.18 - 0.05 * r, export_p, 0.12])),
                'session_hash': f'hash_{rng.integers(1000, 9999)}',
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/events_log.csv', index=False)

    rows, counter = [], 1
    for uid, r in zip(user_ids, risk):
        # Churning accounts accumulate 2-3 failed invoices.
        failures = int(rng.integers(2, 4)) if r > 0.6 else 0
        total = int(rng.integers(4, 8))
        statuses = ['FAILED'] * failures + ['PAID'] * (total - failures)
        rng.shuffle(statuses)
        for status in statuses:
            rows.append({
                'inv_id': f'inv_{counter}',
                'user_id': uid,
                'amount': float(rng.choice([29.99, 99.99, 299.99], p=[0.5, 0.35, 0.15])),
                'status': status,
                'due_date': days_before(rng.integers(0, 180)).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/invoices.csv', index=False)

    rows, counter = [], 1
    for uid, r in zip(user_ids, risk):
        for _ in range(int(rng.poisson(0.4 + 3.0 * r))):
            hot = rng.random() < r
            rows.append({
                'ticket_id': f'tkt_{counter}',
                'user_id': uid,
                'subject': rng.choice(SAAS_CHURN_SUBJECTS if hot else SAAS_ROUTINE_SUBJECTS),
                'sentiment': rng.choice(['Neutral', 'Negative', 'Very Negative'],
                                        p=_norm([0.7 - 0.6 * r, 0.22 + 0.28 * r, 0.08 + 0.32 * r])),
                'status': rng.choice(['OPEN', 'CLOSED'], p=_norm([0.25 + 0.5 * r, 0.75 - 0.5 * r])),
                'opened_at': days_before(rng.integers(0, 90)).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/tickets.csv', index=False)


# -------------------------------------------------------------------- Telecom
def generate_telecom_data():
    rng = np.random.default_rng(SEED + 1)
    sub_ids = [f'sub_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    subs = pd.DataFrame({
        'subscriber_id': sub_ids,
        'plan': [rng.choice(['Prepaid', 'Postpaid'], p=_norm([0.45 + 0.3 * r, 0.55 - 0.3 * r])) for r in risk],
        'region': rng.choice(['North', 'South', 'East', 'West'], ENTITY_COUNT),
        'tenure_months': [max(1, int(rng.integers(2, 72) * (1 - 0.35 * r))) for r in risk],
        'sim_imsi_hash': [f'imsi_{rng.integers(10000, 99999)}' for _ in range(ENTITY_COUNT)],
    })
    subs.to_csv('data/telecom/subscribers.csv', index=False)

    # Churning subscribers see 15-25% dropped calls concentrated on one tower.
    rows, counter = [], 1
    for sid, r in zip(sub_ids, risk):
        volume = int(np.clip(rng.normal(30 * (1 - r) + 4, 5), 2, 90))
        silence = int(rng.integers(0, 3) + r * rng.integers(8, 45))
        drop_rate = float(rng.uniform(0.15, 0.25)) if r > 0.6 else float(rng.uniform(0.02, 0.05))
        bad_tower = rng.choice(['TWR_A', 'TWR_B', 'TWR_C'])
        for _ in range(volume):
            dropped = rng.random() < drop_rate
            # Failures cluster on the subscriber's own weak tower.
            if dropped and r > 0.6:
                tower = bad_tower
            else:
                tower = rng.choice(['TWR_A', 'TWR_B', 'TWR_C'])
            rows.append({
                'call_id': f'call_{counter}',
                'subscriber_id': sid,
                'call_timestamp': days_before(min(silence + rng.exponential(10), 120)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'duration_sec': int(np.clip(rng.normal(420 * (1 - 0.7 * r), 180), 5, 1800)),
                'call_status': 'DROPPED' if dropped else 'COMPLETED',
                'tower_id': tower,
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/network_cdrs.csv', index=False)

    # Recharge gaps widen for the churning cohort: roughly day 5 -> 20 -> 50.
    rows, counter = [], 1
    for sid, r in zip(sub_ids, risk):
        count = int(np.clip(rng.normal(8 * (1 - r) + 2, 2), 2, 20))
        if r > 0.6:
            # Chronologically expanding gaps: 5, 8, 12.8, ... The list is walked
            # in reverse when converting to ages, because age counts backwards
            # from the reference date — building it forwards would make the most
            # recent interval the shortest, inverting the signal.
            gaps = [5.0 * (1.6 ** i) for i in range(count - 1)]
            age = float(rng.integers(0, 6))
            ages = [age]
            for gap in reversed(gaps):
                age += gap
                ages.append(age)
            ages = [min(a, 150) for a in ages]
        else:
            ages = [min(float(rng.integers(0, 5) + rng.exponential(9) + i * 7), 150)
                    for i in range(count)]
        for age in ages:
            rows.append({
                'rec_id': f'rec_{counter}',
                'subscriber_id': sid,
                'amount': int(rng.choice([10, 20, 50, 100],
                                         p=_norm([0.20 + 0.45 * r, 0.35, 0.30 - 0.20 * r, 0.15 - 0.10 * r]))),
                'recharge_date': days_before(age).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/recharge_history.csv', index=False)

    rows, counter = [], 1
    for sid, r in zip(sub_ids, risk):
        for _ in range(int(rng.poisson(0.15 + 2.2 * r))):
            churning = r > 0.6
            category = rng.choice(
                ['MNP_PORT_OUT', 'BILLING', 'NETWORK', 'GENERAL'],
                p=_norm([0.50 * r, 0.25, 0.30, 0.40 - 0.40 * r]))
            rows.append({
                'comp_id': f'comp_{counter}',
                'subscriber_id': sid,
                'category': category,
                'logged_at': days_before(rng.integers(0, 90)).strftime('%Y-%m-%d'),
                'notes': rng.choice(TELECOM_CHURN_NOTES if churning else TELECOM_ROUTINE_NOTES),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/complaints.csv', index=False)


# -------------------------------------------------------------------- FinTech
def generate_fintech_data():
    rng = np.random.default_rng(SEED + 2)
    acc_ids = [f'acc_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    accs = pd.DataFrame({
        'account_id': acc_ids,
        'tier': [rng.choice(['Standard', 'Premium', 'Metal'],
                            p=_norm([0.40 + 0.4 * r, 0.35 - 0.15 * r, 0.25 - 0.25 * r])) for r in risk],
        'created_at': [days_before(rng.integers(60, 900)).strftime('%Y-%m-%d') for _ in range(ENTITY_COUNT)],
        'balance': [round(float(np.clip(rng.normal(3200 * (1 - 0.8 * r), 900), 5, 20000)), 2) for r in risk],
        'device_mac_hash': [f'mac_{rng.integers(1000, 9999)}' for _ in range(ENTITY_COUNT)],
    })
    accs.to_csv('data/fintech/accounts.csv', index=False)

    # Churning accounts skew heavily to WITHDRAWAL in the recent window and
    # carry a run of 3-5 consecutive failed P2P transfers.
    rows, counter = [], 1
    for aid, r in zip(acc_ids, risk):
        volume = int(np.clip(rng.normal(28 * (1 - r) + 3, 5), 3, 80))
        dormancy = int(rng.integers(0, 4) + r * rng.integers(12, 60))
        churning = r > 0.6
        entries = []
        for _ in range(volume):
            age = min(dormancy + rng.exponential(11), 180)
            if churning and age <= 14:
                tx_type = rng.choice(['DEPOSIT', 'WITHDRAWAL', 'P2P'], p=[0.10, 0.70, 0.20])
            else:
                tx_type = rng.choice(['DEPOSIT', 'WITHDRAWAL', 'P2P'],
                                     p=_norm([0.45 - 0.35 * r, 0.25 + 0.35 * r, 0.30]))
            entries.append({
                'tx_id': f'tx_{counter}',
                'account_id': aid,
                'timestamp': days_before(age).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'amount': round(float(rng.uniform(5, 500)), 2),
                'tx_type': tx_type,
                'status': 'FAILED' if rng.random() < 0.03 + 0.20 * r else 'SUCCESS',
                '_age': age,
            })
            counter += 1

        if churning:
            p2p = sorted([e for e in entries if e['tx_type'] == 'P2P'], key=lambda e: -e['_age'])
            for entry in p2p[:int(rng.integers(3, 6))]:
                entry['status'] = 'FAILED'

        for entry in sorted(entries, key=lambda e: -e['_age']):
            entry.pop('_age')
            rows.append(entry)
    pd.DataFrame(rows).to_csv('data/fintech/ledger_transactions.csv', index=False)

    rows, counter = [], 1
    for aid, r in zip(acc_ids, risk):
        decline_rate = float(rng.uniform(0.15, 0.20)) if r > 0.6 else float(rng.uniform(0.01, 0.04))
        for _ in range(int(np.clip(rng.normal(14 * (1 - r) + 2, 4), 1, 45))):
            rows.append({
                'swipe_id': f'swp_{counter}',
                'account_id': aid,
                'swipe_timestamp': days_before(rng.integers(0, 120)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'merchant_category': rng.choice(['GROCERY', 'ENTERTAINMENT', 'TRAVEL', 'DINING']),
                'status': 'DECLINED' if rng.random() < decline_rate else 'APPROVED',
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/fintech/card_swipes.csv', index=False)

    rows, counter = [], 1
    for aid, r in zip(acc_ids, risk):
        count = int(rng.integers(2, 4)) if r > 0.6 else int(rng.poisson(0.15))
        for _ in range(count):
            rows.append({
                'dispute_id': f'dsp_{counter}',
                'account_id': aid,
                'reason': rng.choice(['Fraudulent', 'Not Received', 'Duplicate'],
                                     p=[0.55, 0.25, 0.20] if r > 0.6 else [0.2, 0.4, 0.4]),
                'open_date': days_before(rng.integers(0, 90)).strftime('%Y-%m-%d'),
                'status': rng.choice(['OPEN', 'RESOLVED'], p=_norm([0.3 + 0.5 * r, 0.7 - 0.5 * r])),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/fintech/disputes.csv', index=False)


def _norm(weights):
    """Clamp to non-negative and normalise, so risk-scaled weights stay valid."""
    arr = np.clip(np.asarray(weights, dtype=float), 0.001, None)
    return arr / arr.sum()


if __name__ == '__main__':
    print(f'Generating mock data (reference date {REFERENCE_DATE:%Y-%m-%d})...')
    create_dirs()
    generate_saas_data()
    generate_telecom_data()
    generate_fintech_data()
    for directory in SECTOR_DIRS:
        for name in sorted(os.listdir(directory)):
            df = pd.read_csv(os.path.join(directory, name))
            print(f'  {directory}/{name:<26} {df.shape[0]:>5} rows x {df.shape[1]} cols')
    print(f'Entities 0-{CHURN_COHORT_SIZE - 1} are the churning cohort.')
