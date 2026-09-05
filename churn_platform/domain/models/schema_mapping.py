from pydantic import BaseModel, field_validator
from typing import List

VALID_ROLES = ("DIMENSION", "TIME_SERIES_EVENT", "TRANSACTIONAL", "UNSTRUCTURED_TEXT")


class TableClassification(BaseModel):
    file_name: str
    role: str  # one of VALID_ROLES
    primary_entity_key: str
    timestamp_column: str | None = None
    noise_columns: List[str] = []

    @field_validator("role", mode="before")
    @classmethod
    def _normalise_role(cls, value):
        """
        A language model produces this field, so a near-miss like "DIMENSIONS"
        is likely. Normalise what is recoverable and reject what is not, rather
        than letting a typo flow downstream where it silently changes which
        table is chosen as the base.
        """
        text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
        if text in VALID_ROLES:
            return text
        # Tolerate a trailing plural, the most common near-miss.
        if text.endswith("S") and text[:-1] in VALID_ROLES:
            return text[:-1]
        raise ValueError(f"role must be one of {VALID_ROLES}, got {value!r}")


class SchemaMapping(BaseModel):
    primary_entity_key: str
    tables: List[TableClassification]
