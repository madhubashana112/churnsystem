from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi import Request
from dotenv import load_dotenv
from churn_platform.presentation.api.v1 import tenants, upload, analytics, samples, engine
import os

load_dotenv('api_key.env')

app = FastAPI(title="Domain-Adaptive Churn Prediction API")

app.mount("/static", StaticFiles(directory="churn_platform/presentation/static"), name="static")
templates = Jinja2Templates(directory="churn_platform/presentation/templates")

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

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("churn_platform.main:app", host="0.0.0.0", port=8000, reload=True)
