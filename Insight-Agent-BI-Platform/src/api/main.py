"""
InsightAgent - Enterprise FastAPI Backend Service
Provides high-performance REST APIs for metrics, predictions, and autonomous agent triggers.
"""

import os
import sys
from pathlib import Path

# Automatically ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import sqlite3
import io
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agents.anomaly_agent import AnomalyAgent
from src.agents.nlq_sql_agent import NLQSQLAgent
from src.agents.executive_agent import ExecutiveAgent
from src.data_ingestion import DataIngestionEngine

# Initialize FastAPI App
app = FastAPI(
    title="InsightAgent Autonomous BI & Analytics API",
    description="Enterprise Multi-Agent BI, ML Analytics & Decision Intelligence Platform",
    version="1.0.0"
)

# Enable CORS for Streamlit and cross-origin clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_raw_db = os.getenv("DATABASE_PATH", "data/warehouse.db")
DATABASE_PATH = str(ROOT_DIR / _raw_db) if not os.path.isabs(_raw_db) else _raw_db


# Pydantic Request & Response Schemas
class ChatQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language analytical question")

class AnomalyDiagnosisRequest(BaseModel):
    focus_category: Optional[str] = Field(None, description="Optional category to focus anomaly diagnosis on")

class PipelineRunResponse(BaseModel):
    status: str
    message: str
    records_processed: int

class RealtimeTransactionRequest(BaseModel):
    TransactionID: Optional[str] = Field(None, description="Optional custom transaction ID")
    TransactionDate: Optional[str] = Field(None, description="YYYY-MM-DD date")
    CustomerID: str = Field(..., description="Customer ID, e.g. CUST-0042")
    CustomerName: Optional[str] = Field(None, description="Customer company name")
    CustomerSegment: Optional[str] = Field("Strategic Mid-Market", description="Customer segment tier")
    Region: Optional[str] = Field("North America - East", description="Sales territory")
    State: Optional[str] = Field("New York", description="State or province")
    Channel: Optional[str] = Field("Digital Cloud Portal", description="Channel name")
    ProductID: str = Field(..., description="Product SKU, e.g. PRD-101")
    ProductName: Optional[str] = Field(None, description="Product title")
    Category: Optional[str] = Field(None, description="Product category")
    Quantity: int = Field(1, ge=1, description="Quantity of units")
    UnitPrice: float = Field(..., gt=0, description="Unit price in USD")
    CostPrice: Optional[float] = Field(None, gt=0, description="Cost price in USD")
    DiscountRate: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Discount rate")
    PaymentMethod: Optional[str] = Field("Corporate Net-30", description="Payment method")
    IsReturned: Optional[int] = Field(0, ge=0, le=1, description="1 if returned, else 0")


def check_db_exists():
    """Validates if warehouse.db exists."""
    if not os.path.exists(DATABASE_PATH):
        raise HTTPException(
            status_code=503,
            detail="Enterprise Data Warehouse not found. Please run the data pipeline first via 'python run_pipeline.py'."
        )


@app.get("/")
def root():
    """API Root & Health Status."""
    db_ready = os.path.exists(DATABASE_PATH)
    return {
        "service": "InsightAgent Analytics & Multi-Agent API",
        "status": "Online",
        "version": "1.0.0",
        "warehouse_status": "Ready" if db_ready else "Uninitialized (Run run_pipeline.py)",
        "endpoints": [
            "/health",
            "/api/metrics/summary",
            "/api/anomalies",
            "/api/segments",
            "/api/forecast",
            "/api/agents/chat",
            "/api/agents/diagnose-anomalies",
            "/api/agents/executive-briefing",
            "/api/pipeline/run"
        ]
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "database_connected": os.path.exists(DATABASE_PATH)}


@app.get("/api/metrics/summary")
def get_metrics_summary():
    """Returns top-level enterprise KPIs and scorecard metrics."""
    check_db_exists()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as TotalOrders,
                ROUND(SUM(NetRevenue), 2) as TotalRevenue,
                ROUND(SUM(GrossRevenue), 2) as GrossRevenue,
                ROUND(SUM(Profit), 2) as TotalProfit,
                ROUND(AVG(ProfitMargin), 2) as AvgMarginPct,
                ROUND(AVG(NetRevenue), 2) as AvgOrderValue,
                SUM(IsReturned) as TotalReturns,
                ROUND(AVG(DiscountRate) * 100, 2) as AvgDiscountPct,
                SUM(Anomaly_Flag) as AnomalyCount
            FROM fact_transactions;
        """)
        row = dict(cursor.fetchone())
        row["ReturnRatePct"] = round((row["TotalReturns"] / max(1, row["TotalOrders"])) * 100, 2)

        # Count active customers
        cursor.execute("SELECT COUNT(*) as CustomerCount FROM dim_customer;")
        row["ActiveCustomers"] = cursor.fetchone()["CustomerCount"]

        return {"status": "success", "data": row}
    finally:
        conn.close()


@app.get("/api/anomalies")
def get_anomalies(limit: int = Query(50, ge=1, le=500)):
    """Retrieves top detected operational and financial anomalies."""
    check_db_exists()
    agent = AnomalyAgent(db_path=DATABASE_PATH)
    metrics = agent.get_anomaly_metrics()
    
    # Return formatted anomaly details
    top = metrics.get("top_anomalies", [])[:limit]
    return {
        "status": "success",
        "anomaly_count": metrics.get("anomaly_count", 0),
        "total_revenue_exposed": metrics.get("total_revenue_exposed", 0.0),
        "total_profit_loss": metrics.get("total_profit_loss", 0.0),
        "by_type": metrics.get("by_type", {}),
        "by_category": metrics.get("by_category", {}),
        "anomalies": top
    }


@app.get("/api/segments")
def get_segments():
    """Retrieves RFM customer segmentation summary and distribution."""
    check_db_exists()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM fact_rfm_segments ORDER BY TotalRevenue DESC;")
        rows = [dict(r) for r in cursor.fetchall()]
        return {"status": "success", "segments": rows}
    finally:
        conn.close()


@app.get("/api/forecast")
def get_forecast():
    """Retrieves 30-day future revenue forecasts with confidence bounds."""
    check_db_exists()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM fact_forecasts ORDER BY ForecastDate ASC;")
        rows = [dict(r) for r in cursor.fetchall()]
        total_projected = sum(r["ForecastedRevenue"] for r in rows)
        return {
            "status": "success",
            "model_type": rows[0]["ModelType"] if rows else "N/A",
            "total_projected_revenue": round(total_projected, 2),
            "forecast_days": len(rows),
            "forecast": rows
        }
    finally:
        conn.close()


@app.post("/api/agents/chat")
def natural_language_query(req: ChatQueryRequest):
    """
    Autonomous NLQ-to-SQL Agent:
    Converts question to safe SQL, executes it, and synthesizes answers.
    """
    check_db_exists()
    agent = NLQSQLAgent(db_path=DATABASE_PATH)
    result = agent.ask(req.question)
    return {
        "status": "success",
        "question": result["question"],
        "sql": result["sql"],
        "summary": result["summary"],
        "agent_mode": result["agent_mode"],
        "row_count": result["row_count"],
        "data": result.get("data", [])
    }


@app.post("/api/agents/diagnose-anomalies")
def trigger_anomaly_diagnosis(req: AnomalyDiagnosisRequest = None):
    """
    Autonomous Anomaly Agent:
    Scans Isolation Forest flags and produces a comprehensive root-cause diagnosis.
    """
    check_db_exists()
    agent = AnomalyAgent(db_path=DATABASE_PATH)
    focus = req.focus_category if req else None
    result = agent.run_diagnosis(focus_category=focus)
    return {
        "status": result["status"],
        "diagnosis_markdown": result["diagnosis_markdown"],
        "agent_mode": result["agent_mode"],
        "metrics": {
            "anomaly_count": result["metrics"]["anomaly_count"],
            "total_revenue_exposed": result["metrics"]["total_revenue_exposed"],
            "total_profit_loss": result["metrics"]["total_profit_loss"],
            "by_type": result["metrics"]["by_type"]
        }
    }


@app.post("/api/agents/executive-briefing")
def trigger_executive_briefing():
    """
    Autonomous Executive Agent:
    Generates weekly C-Suite strategic briefing for CEO/CFO.
    """
    check_db_exists()
    agent = ExecutiveAgent(db_path=DATABASE_PATH)
    result = agent.generate_briefing()
    return {
        "status": "success",
        "briefing_markdown": result["briefing_markdown"],
        "agent_mode": result["agent_mode"],
        "timestamp": result["timestamp"]
    }


@app.post("/api/pipeline/run", response_model=PipelineRunResponse)
def trigger_pipeline_refresh():
    """Triggers the full data generation, ML modeling, and warehouse loading pipeline."""
    from src.data_generator import generate_enterprise_dataset
    from src.analytics_engine import AnalyticsEngine
    from src.database import EnterpriseWarehouse

    try:
        # Step 1: Generate data
        raw_df = generate_enterprise_dataset(num_rows=12000)

        # Step 2: ML Analytics
        engine = AnalyticsEngine()
        rfm_df, rfm_summary_df = engine.compute_rfm_segmentation(raw_df)
        scored_txns_df, anomalies_df = engine.detect_anomalies(raw_df)
        forecast_df, _ = engine.forecast_revenue(raw_df, forecast_horizon_days=30)

        # Step 3: Warehouse & Star Schema
        wh = EnterpriseWarehouse()
        star_tables = wh.build_star_schema(
            scored_txns_df=scored_txns_df,
            rfm_df=rfm_df,
            rfm_summary_df=rfm_summary_df,
            anomalies_df=anomalies_df,
            forecast_df=forecast_df
        )
        wh.load_warehouse(star_tables)
        wh.export_powerbi_csvs(star_tables)

        return PipelineRunResponse(
            status="success",
            message="End-to-End Enterprise Analytics Pipeline executed and Warehouse refreshed.",
            records_processed=len(scored_txns_df)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failure: {str(e)}")


@app.get("/api/data/schema-template")
def get_data_schema_template():
    """Returns the schema specification and sample data template for ingestion."""
    engine = DataIngestionEngine(db_path=DATABASE_PATH)
    sample_df = engine.get_template_dataframe()
    return {
        "status": "success",
        "schema_specification": engine.SCHEMA_SPECIFICATION,
        "sample_template": sample_df.to_dict(orient="records"),
        "required_fields": engine.REQUIRED_MINIMAL_COLUMNS
    }


@app.post("/api/data/ingest-realtime")
def ingest_realtime_transaction(txn: RealtimeTransactionRequest):
    """
    Ingests a single live streaming transaction, runs automated data sanitization,
    scores anomaly probability in real time, and commits to the warehouse.
    """
    check_db_exists()
    engine = DataIngestionEngine(db_path=DATABASE_PATH)
    res = engine.ingest_single_realtime_transaction(txn.model_dump(exclude_unset=True))
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message", "Ingestion failed"))
    return res


@app.post("/api/data/upload-batch")
async def upload_batch_data(file: UploadFile = File(...)):
    """
    Uploads a batch CSV or JSON dataset, executes automated cleaning and imputation,
    runs ML scoring, and loads into the warehouse.
    """
    check_db_exists()
    content = await file.read()
    filename = file.filename.lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith(".json"):
            df = pd.read_json(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Only .csv and .json files are supported.")
    except Exception as read_err:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(read_err)}")

    engine = DataIngestionEngine(db_path=DATABASE_PATH)
    cleaned_df, report = engine.validate_and_clean(df, auto_impute=True, remove_duplicates=True)
    if report["errors"]:
        raise HTTPException(status_code=400, detail="; ".join(report["errors"]))

    res = engine.score_and_ingest(cleaned_df)
    res["cleaning_report"] = report
    return res
