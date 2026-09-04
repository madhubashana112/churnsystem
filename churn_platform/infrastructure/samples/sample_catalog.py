"""
Access to the mock datasets bundled under ``data/`` so a tenant can run a
full analysis without having to supply their own tables first.
"""
from pathlib import Path
from typing import Dict, List

import pandas as pd

# churn_platform/infrastructure/samples/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

SECTOR_FOLDERS = {
    "SaaS": "saas",
    "Telecom": "telecom",
    "FinTech": "fintech",
}


def _data_dir() -> Path:
    """The bundled data directory, preferring the package-relative location."""
    packaged = _REPO_ROOT / "data"
    return packaged if packaged.is_dir() else Path.cwd() / "data"


def sector_dir(sector: str) -> Path:
    folder = SECTOR_FOLDERS.get(sector)
    if folder is None:
        raise ValueError(f"Unknown sector: {sector}")
    return _data_dir() / folder


def has_samples(sector: str) -> bool:
    try:
        directory = sector_dir(sector)
    except ValueError:
        return False
    return directory.is_dir() and any(directory.glob("*.csv"))


def list_datasets(sector: str) -> List[dict]:
    """Describe each bundled CSV: name, size and shape."""
    directory = sector_dir(sector)
    if not directory.is_dir():
        return []

    described = []
    for path in sorted(directory.glob("*.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            # A malformed sample should not take the whole listing down.
            continue
        described.append({
            "file_name": path.name,
            "bytes": path.stat().st_size,
            "row_count": int(df.shape[0]),
            "column_count": int(df.shape[1]),
            "columns": [str(c) for c in df.columns][:12],
        })
    return described


def load_dataframes(sector: str) -> Dict[str, pd.DataFrame]:
    """Read every bundled CSV for a sector, keyed by file name."""
    directory = sector_dir(sector)
    if not directory.is_dir():
        return {}
    return {path.name: pd.read_csv(path) for path in sorted(directory.glob("*.csv"))}
