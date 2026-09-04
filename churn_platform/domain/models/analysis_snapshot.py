from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from churn_platform.domain.models.schema_mapping import SchemaMapping


class SourceFile(BaseModel):
    """A table that took part in one analysis run."""
    file_name: str
    row_count: int
    column_count: int


class AnalysisSnapshot(BaseModel):
    """
    The full result of one analysis run, kept so the dashboard can be
    rebuilt without re-uploading and re-scoring the same tables.
    """
    tenant_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "upload"  # "upload" or "sample"
    engine: str = "local"   # "qwen" or "local"
    engine_reason: Optional[str] = None  # why the local engine was used, if it was
    schema_mapping: SchemaMapping
    predictions: List[Dict[str, Any]]
    source_files: List[SourceFile] = []
