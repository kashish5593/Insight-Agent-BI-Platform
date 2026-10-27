"""
InsightAgent - One-Click End-to-End Analytics Pipeline Orchestrator
Executes:
1. Enterprise Data Generator (12,000+ transactions with injected anomalies)
2. Machine Learning Analytics Engine (K-Means RFM, Isolation Forest, Holt-Winters Forecasting)
3. Star-Schema Dimensional Modeling & SQLite Warehouse Ingestion
4. Power BI Desktop CSV Exports
"""

import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv()

from src.data_generator import generate_enterprise_dataset
from src.analytics_engine import AnalyticsEngine
from src.database import EnterpriseWarehouse


def run_full_pipeline(num_rows: int = 12000):
    """Executes the complete production data pipeline."""
    start_time = time.time()
    print("=" * 80)
    print("  INSIGHTAGENT: AUTONOMOUS MULTI-AGENT BI & ADVANCED ANALYTICS PLATFORM")
    print("  End-to-End Enterprise Pipeline Execution")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target Record Count: {num_rows:,} enterprise transactions\n")

    # Step 1: Generate Enterprise Data
    print("[PHASE 1/4] Synthetic Enterprise Data Ingestion...")
    raw_df = generate_enterprise_dataset(num_rows=num_rows)
    print(f"  -> Generated {len(raw_df):,} raw records across {raw_df['CustomerID'].nunique()} accounts.\n")

    # Step 2: Machine Learning & Analytics Engine
    print("[PHASE 2/4] Executing Advanced Machine Learning & Statistical Modeling...")
    engine = AnalyticsEngine(random_state=42)

    # 2.1 RFM Segmentation
    rfm_df, rfm_summary_df = engine.compute_rfm_segmentation(raw_df)
    
    # 2.2 Anomaly Detection
    scored_txns_df, anomalies_df = engine.detect_anomalies(raw_df, contamination=0.015)

    # 2.3 Time-Series Forecasting
    forecast_df, forecast_summary = engine.forecast_revenue(scored_txns_df, forecast_horizon_days=30)
    print(f"  -> 30-Day Projected Revenue: ${forecast_summary['Projected30dRevenue']:,.2f} ({forecast_summary['ModelName']})\n")

    # Step 3: Star-Schema Dimensional Modeling
    print("[PHASE 3/4] Modeling Enterprise Star-Schema & Loading SQLite Warehouse...")
    warehouse = EnterpriseWarehouse(
        db_path="data/warehouse.db",
        powerbi_dir="data/powerbi_exports"
    )
    star_tables = warehouse.build_star_schema(
        scored_txns_df=scored_txns_df,
        rfm_df=rfm_df,
        rfm_summary_df=rfm_summary_df,
        anomalies_df=anomalies_df,
        forecast_df=forecast_df
    )
    warehouse.load_warehouse(star_tables)
    print()

    # Step 4: Power BI CSV Exports
    print("[PHASE 4/4] Exporting Clean CSV Datasets for Power BI Desktop...")
    exported_csvs = warehouse.export_powerbi_csvs(star_tables)
    print()

    elapsed = round(time.time() - start_time, 2)
    print("=" * 80)
    print(f"  [SUCCESS] PIPELINE COMPLETED SUCCESSFULLY IN {elapsed} SECONDS")
    print("=" * 80)
    print("\nWarehouse Summary:")
    print(f"  - Database File:           data/warehouse.db")
    print(f"  - Total Transactions:      {len(scored_txns_df):,}")
    print(f"  - Segmented Customers:     {len(rfm_df):,}")
    print(f"  - Detected Anomalies:      {len(anomalies_df):,} ({len(anomalies_df)/len(scored_txns_df)*100:.2f}%)")
    print(f"  - Forecast Data Points:    {len(forecast_df):,} days")
    print(f"  - Power BI CSV Exports:    {len(exported_csvs)} files in data/powerbi_exports/")
    print("\nNext Steps:")
    print("  1. Launch Backend API:      uvicorn src.api.main:app --reload --port 8000")
    print("  2. Launch BI Dashboard:     streamlit run dashboard/app.py")
    print("  3. Power BI Integration:   Review powerbi/POWER_BI_BUILD_GUIDE.md")
    print("=" * 80)


if __name__ == "__main__":
    run_full_pipeline()
