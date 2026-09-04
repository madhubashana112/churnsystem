from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from typing import List
import pandas as pd
import io
from churn_platform.presentation.api.dependencies import get_schema_resolver, get_feature_synthesizer, get_sector_core, get_tenant_repo
from churn_platform.application.use_cases.resolve_multi_sheet_schema import ResolveMultiSheetSchemaUseCase
from churn_platform.application.use_cases.synthesize_features import SynthesizeFeaturesUseCase
from churn_platform.application.use_cases.execute_sector_analysis import ExecuteSectorAnalysisUseCase

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/analyze")
async def upload_and_analyze(
    tenant_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    repo = get_tenant_repo()
    tenant = await repo.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    core = get_sector_core(tenant.sector)
    
    file_samples = {}
    dataframes = {}
    
    for file in files:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        dataframes[file.filename] = df
        
        # Take headers and first 3 rows
        sample_csv = df.head(3).to_csv(index=False)
        file_samples[file.filename] = sample_csv

    # 1. Resolve Schema
    resolver = get_schema_resolver()
    resolve_uc = ResolveMultiSheetSchemaUseCase(resolver)
    schema = await resolve_uc.execute(file_samples)
    
    # 2. Synthesize Features
    synthesizer = get_feature_synthesizer()
    synth_uc = SynthesizeFeaturesUseCase(synthesizer)
    features = synth_uc.execute(schema, dataframes)
    
    # 3. Execute Core Analysis
    analyze_uc = ExecuteSectorAnalysisUseCase()
    # Batch limit for MVP
    results = await analyze_uc.execute(core, features[:20]) 
    
    # Format output
    output_predictions = []
    for pred, playbook in results:
        output_predictions.append({
            "prediction": pred.model_dump(),
            "playbook": playbook.model_dump()
        })
        
    return {
        "schema_mapping": schema.model_dump(),
        "predictions": output_predictions
    }
