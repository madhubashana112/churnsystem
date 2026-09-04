from pydantic import BaseModel
from typing import List, Dict

class TableClassification(BaseModel):
    file_name: str
    role: str # DIMENSION, TIME_SERIES_EVENT, TRANSACTIONAL, UNSTRUCTURED_TEXT
    primary_entity_key: str
    timestamp_column: str | None = None
    noise_columns: List[str] = []

class SchemaMapping(BaseModel):
    primary_entity_key: str
    tables: List[TableClassification]
