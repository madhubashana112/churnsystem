"""
Turns uploaded files into named DataFrames.

Excel workbooks are expanded sheet by sheet: a single .xlsx often holds the
tables that a CSV user would upload separately, and reading only the first sheet
silently discards the rest. Each sheet becomes its own entry keyed
``workbook.xlsx::SheetName``, so the schema resolver sees them as peers of any
CSVs uploaded alongside.
"""
import io
import logging
from typing import Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
SHEET_SEPARATOR = "::"


class UnreadableFile(ValueError):
    """The upload could not be turned into at least one usable table."""


def _validate(df: pd.DataFrame, label: str) -> pd.DataFrame:
    # pandas turns some binary blobs into a 0-row frame; that is not a table.
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise UnreadableFile(f"{label} parsed to an empty table")
    return df


def read_upload(filename: str, contents: bytes) -> Dict[str, pd.DataFrame]:
    """
    One upload to one-or-more named tables.

    Raises UnreadableFile when nothing usable came out, so the caller can report
    the filename rather than failing the whole request.
    """
    name = filename or "upload"

    if name.lower().endswith(EXCEL_SUFFIXES):
        try:
            sheets = pd.read_excel(io.BytesIO(contents), sheet_name=None, engine="openpyxl")
        except Exception as exc:
            raise UnreadableFile(f"{name} is not a readable workbook: {exc}") from exc

        out: Dict[str, pd.DataFrame] = {}
        for sheet_name, df in (sheets or {}).items():
            label = f"{name}{SHEET_SEPARATOR}{sheet_name}"
            try:
                out[label] = _validate(df, label)
            except UnreadableFile:
                # An empty tab is normal in a real workbook; skip it quietly.
                logger.info("Skipping empty sheet %s", label)

        if not out:
            raise UnreadableFile(f"{name} contained no non-empty sheets")
        return out

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as exc:
        raise UnreadableFile(f"{name} is not readable as CSV: {exc}") from exc

    return {name: _validate(df, name)}


def read_uploads(files: List[Tuple[str, bytes]]) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    Returns (tables, unreadable_filenames).

    One bad file among several must not lose the whole upload.
    """
    tables: Dict[str, pd.DataFrame] = {}
    unreadable: List[str] = []

    for filename, contents in files:
        try:
            tables.update(read_upload(filename, contents))
        except UnreadableFile as exc:
            logger.warning("Skipping unreadable upload: %s", exc)
            unreadable.append(filename)

    return tables, unreadable
