# Domain-Adaptive Churn Prediction Platform

An AI-powered multi-tenant churn prediction platform that dynamically adapts to different industry verticals (SaaS, FinTech, Telecom) with automated schema mapping, data ingestion, risk scoring, and interactive analytics dashboards.

## Features

- **Multi-Tenant Architecture**: Supports multiple business verticals with industry-specific schemas and churn risk factors.
- **Domain Adaptation**: Intelligent schema alignment and semantic understanding across different data formats.
- **Automated Ingestion**: Upload CSV/Excel datasets for automated validation and processing.
- **Analytics & Insights**: Churn risk calculation, key risk driver analysis, and retention recommendations.
- **Interactive UI & REST API**: Modern web dashboard built with FastAPI, Jinja2 templates, and responsive frontend components.

## Project Structure

`	ext
├── churn_platform/
│   ├── application/       # Business logic and services
│   ├── domain/            # Domain entities and interfaces
│   ├── infrastructure/    # Data storage, external integrations, adapters
│   ├── presentation/      # FastAPI routes, Jinja templates, static assets
│   └── main.py            # Application entrypoint
├── data/                  # Sample mock datasets (FinTech, SaaS, Telecom)
├── generate_mock_data.py  # Mock dataset generator
├── requirements.txt       # Python dependencies
└── api_key.env.example    # Environment variable template
`

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Setup Virtual Environment
`ash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
`

### 3. Install Dependencies
`ash
pip install -r requirements.txt
`

### 4. Configuration
Copy the sample environment file and add your credentials:
`ash
cp api_key.env.example api_key.env
`

### 5. Generate Mock Data (Optional)
`ash
python generate_mock_data.py
`

### 6. Run the Application
`ash
uvicorn churn_platform.main:app --host 127.0.0.1 --port 8000 --reload
`

Open your browser and navigate to:
- **Onboarding**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Dashboard**: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
