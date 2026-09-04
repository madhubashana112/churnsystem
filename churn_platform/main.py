from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from dotenv import load_dotenv
from churn_platform.presentation.api.v1 import tenants, upload, analytics
import os

load_dotenv('api_key.env')

app = FastAPI(title="Domain-Adaptive Churn Prediction API")

app.mount("/static", StaticFiles(directory="churn_platform/presentation/static"), name="static")
templates = Jinja2Templates(directory="churn_platform/presentation/templates")

app.include_router(tenants.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("churn_platform.main:app", host="0.0.0.0", port=8000, reload=True)
