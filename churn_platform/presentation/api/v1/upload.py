import io
import logging
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from churn_platform.presentation.api.dependencies import (
    ENGINE_MODES,
    api_key_configured,
    default_engine_mode,
    get_analysis_repo,
    get_feature_synthesizer,
    get_local_schema_resolver,
    get_local_sector_core,
    get_schema_resolver,
    get_sector_core,
    get_tenant_repo,
    note_qwen_failure,
    note_qwen_success,
    qwen_cooling_down,
    qwen_last_reason,
)
from churn_platform.application.use_cases.resolve_multi_sheet_schema import ResolveMultiSheetSchemaUseCase
from churn_platform.application.use_cases.synthesize_features import SynthesizeFeaturesUseCase
from churn_platform.application.use_cases.execute_sector_analysis import ExecuteSectorAnalysisUseCase
from churn_platform.domain.models.analysis_snapshot import AnalysisSnapshot, SourceFile
from churn_platform.domain.models.tenant import Tenant
from churn_platform.infrastructure.samples import sample_catalog
from churn_platform.infrastructure.parsers.file_ingestion import read_uploads
from churn_platform.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

_settings = get_settings()
# Each batch costs one model call on the Qwen path, so it is capped far lower
# than the local engine, which is free and scores the whole cohort.
MAX_ENTITIES = _settings.max_entities
MAX_ENTITIES_LOCAL = _settings.max_entities_local


async def _resolve_tenant(tenant_id: str) -> Tenant:
    tenant = await get_tenant_repo().get(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found. The server may have restarted — register the workspace again.",
        )
    return tenant


def _normalise_mode(requested: Optional[str]) -> str:
    mode = (requested or "").strip().lower()
    return mode if mode in ENGINE_MODES else default_engine_mode()


def _skip_qwen(mode: str) -> Optional[str]:
    """Why Qwen should not be attempted, or None to go ahead."""
    if mode == "local":
        return None
    if not api_key_configured():
        return "No API key is configured."
    if qwen_cooling_down():
        return qwen_last_reason() or "Qwen was unavailable on a recent request."
    return None


async def _resolve_schema(file_samples: Dict[str, str], mode: str):
    """Returns (schema, engine_used, fallback_reason)."""
    skip = _skip_qwen(mode)
    if mode == "local" or (mode == "auto" and skip):
        schema = await ResolveMultiSheetSchemaUseCase(get_local_schema_resolver()).execute(file_samples)
        return schema, "local", None if mode == "local" else skip

    try:
        schema = await ResolveMultiSheetSchemaUseCase(get_schema_resolver()).execute(file_samples)
        note_qwen_success()
        return schema, "qwen", None
    except Exception as exc:
        reason = _short_reason(exc)
        note_qwen_failure(reason)
        if mode == "qwen":
            raise HTTPException(status_code=502, detail=f"Qwen schema resolution failed: {exc}") from exc
        logger.warning("Qwen schema resolution failed, using the local engine: %s", exc)
        schema = await ResolveMultiSheetSchemaUseCase(get_local_schema_resolver()).execute(file_samples)
        return schema, "local", reason


async def _score(features, tenant: Tenant, mode: str):
    """Returns (results, engine_used, fallback_reason)."""
    use_case = ExecuteSectorAnalysisUseCase()

    skip = _skip_qwen(mode)
    if mode == "local" or (mode == "auto" and skip):
        results = await use_case.execute(get_local_sector_core(tenant.sector), features[:MAX_ENTITIES_LOCAL])
        return results, "local", None if mode == "local" else skip

    try:
        results = await use_case.execute(get_sector_core(tenant.sector), features[:MAX_ENTITIES])
        note_qwen_success()
        return results, "qwen", None
    except Exception as exc:
        reason = _short_reason(exc)
        note_qwen_failure(reason)
        if mode == "qwen":
            raise HTTPException(status_code=502, detail=f"Qwen scoring failed: {exc}") from exc
        logger.warning("Qwen scoring failed, using the local engine: %s", exc)
        results = await use_case.execute(get_local_sector_core(tenant.sector), features[:MAX_ENTITIES_LOCAL])
        return results, "local", reason


def _short_reason(exc: Exception) -> str:
    text = str(exc)
    if "invalid_api_key" in text or "Incorrect API key" in text or "401" in text:
        return "The configured Qwen API key was rejected (401)."
    if "429" in text or "rate" in text.lower():
        return "Qwen rate-limited the request."
    return f"Qwen was unavailable: {text[:140]}"


async def _run_pipeline(tenant: Tenant, dataframes: Dict[str, pd.DataFrame],
                        source: str, mode: str) -> dict:
    """Schema resolution -> feature synthesis -> sector scoring, then persist."""
    if not dataframes:
        raise HTTPException(status_code=400, detail="No readable tables were supplied.")

    # Headers plus the first 5 rows are enough to classify a table.
    file_samples = {name: df.head(5).to_csv(index=False) for name, df in dataframes.items()}

    schema, schema_engine, schema_reason = await _resolve_schema(file_samples, mode)

    features = SynthesizeFeaturesUseCase(get_feature_synthesizer()).execute(
        schema, dataframes, sector=tenant.sector
    )
    if not features:
        raise HTTPException(
            status_code=422,
            detail="The tables were parsed but no entities could be derived. "
                   "Check that they share a common id column.",
        )

    results, score_engine, score_reason = await _score(features, tenant, mode)

    predictions = [
        {"prediction": pred.model_dump(), "playbook": playbook.model_dump()}
        for pred, playbook in results
    ]

    engine = "qwen" if score_engine == "qwen" else "local"
    reason = score_reason or schema_reason

    snapshot = AnalysisSnapshot(
        tenant_id=tenant.tenant_id,
        source=source,
        engine=engine,
        engine_reason=reason,
        schema_mapping=schema,
        predictions=predictions,
        source_files=[
            SourceFile(file_name=name, row_count=int(df.shape[0]), column_count=int(df.shape[1]))
            for name, df in dataframes.items()
        ],
    )
    await get_analysis_repo().save(snapshot)

    return {
        "schema_mapping": snapshot.schema_mapping.model_dump(),
        "predictions": snapshot.predictions,
        "source_files": [f.model_dump() for f in snapshot.source_files],
        "created_at": snapshot.created_at.isoformat(),
        "source": snapshot.source,
        "engine": engine,
        "engine_reason": reason,
        "feature_count": len(features[0].features) if features else 0,
        "entities_total": len(features),
        "entities_scored": len(predictions),
    }


@router.post("/analyze")
async def upload_and_analyze(
    tenant_id: str = Form(...),
    engine: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    tenant = await _resolve_tenant(tenant_id)

    # Excel workbooks expand to one table per sheet, so a single .xlsx can carry
    # everything a CSV user would upload as separate files.
    uploads = [(f.filename, await f.read()) for f in files]
    dataframes, unreadable = read_uploads(uploads)

    if not dataframes:
        raise HTTPException(
            status_code=400,
            detail=f"None of the uploaded files could be parsed: {', '.join(unreadable) or 'no files'}.",
        )

    result = await _run_pipeline(tenant, dataframes, source="upload", mode=_normalise_mode(engine))
    result["unreadable_files"] = unreadable
    return result


@router.post("/analyze-sample")
async def analyze_bundled_sample(
    tenant_id: str = Form(...),
    engine: Optional[str] = Form(None),
):
    """Run the same pipeline against the mock dataset bundled for this sector."""
    tenant = await _resolve_tenant(tenant_id)

    dataframes = sample_catalog.load_dataframes(tenant.sector)
    if not dataframes:
        raise HTTPException(
            status_code=404,
            detail=f"No bundled sample dataset is available for {tenant.sector}.",
        )

    return await _run_pipeline(tenant, dataframes, source="sample", mode=_normalise_mode(engine))
