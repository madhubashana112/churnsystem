from fastapi import APIRouter, HTTPException

from churn_platform.infrastructure.samples import sample_catalog

router = APIRouter(prefix="/samples", tags=["Samples"])


@router.get("/{sector}")
async def list_sample_dataset(sector: str):
    """Describe the mock dataset bundled for a sector, without loading it into an analysis."""
    if sector not in sample_catalog.SECTOR_FOLDERS:
        raise HTTPException(status_code=400, detail="Invalid sector. Must be SaaS, Telecom, or FinTech.")

    datasets = sample_catalog.list_datasets(sector)
    return {
        "sector": sector,
        "available": bool(datasets),
        "file_count": len(datasets),
        "total_rows": sum(d["row_count"] for d in datasets),
        "files": datasets,
    }
