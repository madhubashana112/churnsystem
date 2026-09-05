from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi import Request, HTTPException
from dotenv import load_dotenv
from churn_platform.presentation.api.v1 import tenants, upload, analytics, samples, engine
from pathlib import Path
import os

# Resolve everything from the package, not the working directory: serverless
# hosts invoke the app from a different cwd than a local `uvicorn` run.
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / "api_key.env")

app = FastAPI(title="Domain-Adaptive Churn Prediction API")

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "presentation" / "static"),
    name="static",
)
templates = Jinja2Templates(directory=BASE_DIR / "presentation" / "templates")


def _asset_version() -> str:
    """
    Short fingerprint of the front-end assets.

    StaticFiles serves CSS and JS with no cache-busting, so a returning browser
    keeps the previous deployment's script and silently runs old code against a
    new API. Appending this to the asset URLs makes each build a fresh URL.
    """
    static_dir = BASE_DIR / "presentation" / "static"
    newest = 0.0
    for path in static_dir.rglob("*"):
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
    return format(int(newest), "x")


templates.env.globals["asset_version"] = _asset_version()

app.include_router(tenants.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(samples.router, prefix="/api/v1")
app.include_router(engine.router, prefix="/api/v1")

FAVICON = (
    b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    b"<rect width='24' height='24' rx='6' fill='#6366f1'/>"
    b"<path d='M20 12h-3l-2.5 7L10 5l-2.5 7H4' fill='none' stroke='white' "
    b"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Browsers request this regardless of the inline <link>; serve it rather than 404."""
    return Response(content=FAVICON, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

SECTOR_TEMPLATES = {
    "saas": "dashboard_saas.html",
    "telecom": "dashboard_telecom.html",
    "fintech": "dashboard_fintech.html",
}


@app.get("/dashboard/{sector}", response_class=HTMLResponse)
async def read_sector_dashboard(request: Request, sector: str):
    """
    Each vertical gets its own template extending base.html, so its KPI cards
    live in the template rather than being toggled at runtime.
    """
    template = SECTOR_TEMPLATES.get(sector.strip().lower())
    if template is None:
        raise HTTPException(status_code=404, detail=f"Unknown sector: {sector}")
    return templates.TemplateResponse(request=request, name=template)


@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("churn_platform.main:app", host="0.0.0.0", port=8000, reload=True)
