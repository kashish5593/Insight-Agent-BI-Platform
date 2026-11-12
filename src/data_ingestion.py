"""
InsightAgent - Data Ingestion, Cleaning & Real-Time Pipeline Engine
Handles real-time transaction streams, batch file uploads, automated schema validation,
data sanitization, outlier cleaning, and incremental warehouse updates.
"""

import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent


class DataIngestionEngine:
    """
    Production Data Ingestion & Sanitization Engine.
    Cleans raw external datasets and streams real-time transactions into the SQLite warehouse.
    """

    REQUIRED_MINIMAL_COLUMNS = ["CustomerID", "ProductID", "Quantity", "UnitPrice"]

    SCHEMA_SPECIFICATION = {
        "TransactionID": {
            "type": "string",
            "required": False,
            "description": "Unique transaction identifier (e.g. 'TXN-90001'). Auto-generated if omitted."
        },
        "TransactionDate": {
            "type": "date (YYYY-MM-DD)",
            "required": False,
            "description": "Date of transaction. Defaults to today's date if omitted."
        },
        "CustomerID": {
            "type": "string",
            "required": True,
            "description": "Customer identifier (e.g. 'CUST-0042')."
        },
        "CustomerName": {
            "type": "string",
            "required": False,
            "description": "Company name. Auto-inferred from warehouse or generated if omitted."
        },
        "CustomerSegment": {
            "type": "string",
            "required": False,
            "description": "Enterprise Tier 1, Strategic Mid-Market, Emerging SMB, Government & Edu."
        },
        "Region": {
            "type": "string",
            "required": False,
            "description": "North America - East/West/Midwest/South, EMEA, APAC. Defaults to 'North America - East'."
        },
        "State": {
            "type": "string",
            "required": False,
            "description": "State or Province name."
        },
        "Channel": {
            "type": "string",
            "required": False,
            "description": "Sales channel (Direct Sales Enterprise, Digital Cloud Portal, Strategic Partner Reseller)."
        },
        "ProductID": {
            "type": "string",
            "required": True,
            "description": "Product SKU identifier (e.g. 'PRD-101')."
        },
        "ProductName": {
            "type": "string",
            "required": False,
            "description": "Product title. Looked up from product catalog if omitted."
        },
        "Category": {
            "type": "string",
            "required": False,
            "description": "Product category taxonomy. Looked up from catalog if omitted."
        },
        "Quantity": {
            "type": "integer (>= 1)",
            "required": True,
            "description": "Number of units ordered. Automatically clipped to >= 1."
        },
        "UnitPrice": {
            "type": "float (> 0)",
            "required": True,
            "description": "Unit selling price in USD."
        },
        "CostPrice": {
            "type": "float (> 0)",
            "required": False,
            "description": "Unit manufacturing/acquisition cost. Estimated from margin profile if omitted."
        },
        "DiscountRate": {
            "type": "float (0.0 to 1.0)",
            "required": False,
            "description": "Discount fraction (e.g. 0.15 for 15%). Defaults to 0.0."
        },
        "PaymentMethod": {
            "type": "string",
            "required": False,
            "description": "Corporate Net-30, Wire Transfer, Credit Line, ACH. Defaults to 'Corporate Net-30'."
        },
        "IsReturned": {
            "type": "integer (0 or 1)",
            "required": False,
            "description": "Whether the order was returned. Defaults to 0."
        }
    }

    def __init__(self, db_path: str = "data/warehouse.db"):
        if not os.path.isabs(db_path) and not os.path.exists(db_path):
            candidate = ROOT_DIR / db_path
            if candidate.exists():
                db_path = str(candidate)
        self.db_path = db_path

    def get_template_dataframe(self) -> pd.DataFrame:
        """Returns a sample template DataFrame illustrating the expected format."""
        sample_rows = [
            {
                "TransactionID": "TXN-DEMO-001",
                "TransactionDate": datetime.now().strftime("%Y-%m-%d"),
                "CustomerID": "CUST-0012",
                "CustomerName": "Omni Tech Enterprises LLC",
                "CustomerSegment": "Enterprise Tier 1",
                "Region": "North America - West",
                "State": "California",
                "Channel": "Direct Sales Enterprise",
                "ProductID": "PRD-201",
                "ProductName": "InsightAgent Autonomous Intelligence Seat",
                "Category": "AI & Analytics",
                "UnitPrice": 480.00,
                "CostPrice": 110.00,
                "Quantity": 15,
                "DiscountRate": 0.10,
                "PaymentMethod": "Corporate Net-30",
                "IsReturned": 0
            },
            {
                "TransactionID": "TXN-DEMO-002",
                "TransactionDate": datetime.now().strftime("%Y-%m-%d"),
                "CustomerID": "CUST-0088",
                "CustomerName": "Vertex Systems Inc.",
                "CustomerSegment": "Strategic Mid-Market",
                "Region": "North America - East",
                "State": "New York",
                "Channel": "Digital Cloud Portal",
                "ProductID": "PRD-101",
                "ProductName": "Enterprise Cloud Compute Node (64 vCPU)",
                "Category": "Cloud Infrastructure",
                "UnitPrice": 1250.00,
                "CostPrice": 520.00,
                "Quantity": 4,
                "DiscountRate": 0.05,
                "PaymentMethod": "Wire Transfer",
                "IsReturned": 0
            }
        ]
        return pd.DataFrame(sample_rows)

    def validate_and_clean(
        self,
        raw_df: pd.DataFrame,
        auto_impute: bool = True,
        remove_duplicates: bool = True
    ) -> Tuple[pd.DataFrame, dict]:
        """
        Comprehensive data validation and automated cleaning pipeline:
        1. Checks for required minimum columns
        2. Imputes missing fields from dimensional catalogs or defaults
        3. Sanitizes numeric bounds (Quantity >= 1, UnitPrice > 0, DiscountRate [0, 1])
        4. Calculates all derived financial columns
        5. Reports cleaning metrics and anomalies handled
        """
        report = {
            "original_rows": len(raw_df),
            "cleaned_rows": 0,
            "duplicates_removed": 0,
            "missing_values_imputed": 0,
            "bounds_corrected": 0,
            "errors": []
        }

        if raw_df.empty:
            report["errors"].append("The uploaded dataset contains 0 rows.")
            return pd.DataFrame(), report

        df = raw_df.copy()

        # Check required columns
        missing_req = [c for c in self.REQUIRED_MINIMAL_COLUMNS if c not in df.columns]
        if missing_req:
            report["errors"].append(f"Missing required columns: {', '.join(missing_req)}")
            return pd.DataFrame(), report

        # 1. Handle Transaction ID
        if "TransactionID" not in df.columns or df["TransactionID"].isnull().all():
            df["TransactionID"] = [f"TXN-LIVE-{uuid.uuid4().hex[:8].upper()}" for _ in range(len(df))]
        else:
            df["TransactionID"] = df["TransactionID"].fillna("").astype(str).str.strip()
            mask_empty_id = df["TransactionID"] == ""
            if mask_empty_id.any():
                df.loc[mask_empty_id, "TransactionID"] = [f"TXN-LIVE-{uuid.uuid4().hex[:8].upper()}" for _ in range(mask_empty_id.sum())]

        # Deduplication
        if remove_duplicates:
            before_dedup = len(df)
            df = df.drop_duplicates(subset=["TransactionID"], keep="first")
            report["duplicates_removed"] = before_dedup - len(df)

        # 2. Date normalization
        if "TransactionDate" not in df.columns:
            df["TransactionDate"] = datetime.now().strftime("%Y-%m-%d")
        else:
            # Parse dates flexibly
            df["TransactionDate"] = pd.to_datetime(df["TransactionDate"], errors="coerce")
            null_dates = df["TransactionDate"].isnull()
            if null_dates.any():
                df.loc[null_dates, "TransactionDate"] = datetime.now()
                report["missing_values_imputed"] += null_dates.sum()
            df["TransactionDate"] = df["TransactionDate"].dt.strftime("%Y-%m-%d")

        # 3. Numeric bounds & type sanitization
        # Quantity
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(1)
        bad_qty = df["Quantity"] < 1
        if bad_qty.any():
            df.loc[bad_qty, "Quantity"] = 1
            report["bounds_corrected"] += bad_qty.sum()
        df["Quantity"] = df["Quantity"].astype(int)

        # UnitPrice
        df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
        bad_price = df["UnitPrice"].isnull() | (df["UnitPrice"] <= 0)
        if bad_price.any():
            median_p = df.loc[~bad_price, "UnitPrice"].median() if (~bad_price).any() else 500.0
            df.loc[bad_price, "UnitPrice"] = median_p
            report["bounds_corrected"] += bad_price.sum()
        df["UnitPrice"] = df["UnitPrice"].round(2)

        # DiscountRate
        if "DiscountRate" not in df.columns:
            df["DiscountRate"] = 0.0
        else:
            df["DiscountRate"] = pd.to_numeric(df["DiscountRate"], errors="coerce").fillna(0.0)
            # If discounts given as percentage > 1 (e.g. 15 instead of 0.15), normalize
            gt_one = df["DiscountRate"] > 1.0
            if gt_one.any():
                df.loc[gt_one, "DiscountRate"] = (df.loc[gt_one, "DiscountRate"] / 100.0).clip(0.0, 0.99)
            df["DiscountRate"] = df["DiscountRate"].clip(lower=0.0, upper=0.99).round(2)

        # CostPrice
        if "CostPrice" not in df.columns or df["CostPrice"].isnull().all():
            # Estimate standard 45% COGS margin
            df["CostPrice"] = (df["UnitPrice"] * 0.45).round(2)
            report["missing_values_imputed"] += len(df)
        else:
            df["CostPrice"] = pd.to_numeric(df["CostPrice"], errors="coerce")
            null_cost = df["CostPrice"].isnull() | (df["CostPrice"] <= 0)
            if null_cost.any():
                df.loc[null_cost, "CostPrice"] = (df.loc[null_cost, "UnitPrice"] * 0.45).round(2)
                report["missing_values_imputed"] += null_cost.sum()
            df["CostPrice"] = df["CostPrice"].round(2)

        # 4. Text & Categorical defaults
        if "CustomerID" not in df.columns:
            df["CustomerID"] = "CUST-LIVE-001"
        else:
            df["CustomerID"] = df["CustomerID"].astype(str).str.strip().str.upper()

        if "CustomerName" not in df.columns:
            df["CustomerName"] = df["CustomerID"].apply(lambda cid: f"Account {cid}")
        else:
            df["CustomerName"] = df["CustomerName"].fillna(df["CustomerID"].apply(lambda cid: f"Account {cid}")).astype(str).str.strip()

        if "CustomerSegment" not in df.columns:
            df["CustomerSegment"] = "Strategic Mid-Market"
        else:
            df["CustomerSegment"] = df["CustomerSegment"].fillna("Strategic Mid-Market").astype(str).str.strip()

        if "Region" not in df.columns:
            df["Region"] = "North America - East"
        else:
            df["Region"] = df["Region"].fillna("North America - East").astype(str).str.strip()

        if "State" not in df.columns:
            df["State"] = "New York"
        else:
            df["State"] = df["State"].fillna("New York").astype(str).str.strip()

        if "Channel" not in df.columns:
            df["Channel"] = "Digital Cloud Portal"
        else:
            df["Channel"] = df["Channel"].fillna("Digital Cloud Portal").astype(str).str.strip()

        if "ProductID" not in df.columns:
            df["ProductID"] = "PRD-GEN-01"
        else:
            df["ProductID"] = df["ProductID"].astype(str).str.strip().str.upper()

        if "ProductName" not in df.columns:
            df["ProductName"] = df["ProductID"].apply(lambda pid: f"Enterprise Item {pid}")
        else:
            df["ProductName"] = df["ProductName"].fillna(df["ProductID"].apply(lambda pid: f"Enterprise Item {pid}")).astype(str).str.strip()

        if "Category" not in df.columns:
            df["Category"] = "Cloud Infrastructure"
        else:
            df["Category"] = df["Category"].fillna("Cloud Infrastructure").astype(str).str.strip()

        if "PaymentMethod" not in df.columns:
            df["PaymentMethod"] = "Corporate Net-30"
        else:
            df["PaymentMethod"] = df["PaymentMethod"].fillna("Corporate Net-30").astype(str).str.strip()

        if "IsReturned" not in df.columns:
            df["IsReturned"] = 0
        else:
            df["IsReturned"] = pd.to_numeric(df["IsReturned"], errors="coerce").fillna(0).astype(int).clip(0, 1)

        # 5. Derive Financial Calculations
        df["GrossRevenue"] = (df["Quantity"] * df["UnitPrice"]).round(2)
        df["DiscountAmount"] = (df["GrossRevenue"] * df["DiscountRate"]).round(2)
        df["NetRevenue"] = (df["GrossRevenue"] - df["DiscountAmount"]).round(2)
        df["TotalCost"] = (df["Quantity"] * df["CostPrice"]).round(2)
        df["Profit"] = (df["NetRevenue"] - df["TotalCost"]).round(2)
        df["ProfitMargin"] = np.where(df["NetRevenue"] > 0, ((df["Profit"] / df["NetRevenue"]) * 100).round(2), 0.0)

        report["cleaned_rows"] = len(df)
        return df, report

    def score_and_ingest(
        self,
        cleaned_df: pd.DataFrame,
        powerbi_dir: str = "data/powerbi_exports"
    ) -> dict:
        """
        Scores incoming records using the trained ML anomaly and segmentation logic,
        commits them to the SQLite warehouse, and refreshes the Power BI export CSVs.
        """
        if cleaned_df.empty:
            return {"status": "error", "message": "No valid data to ingest.", "records_ingested": 0}

        if not os.path.isabs(powerbi_dir) and not os.path.exists(powerbi_dir):
            candidate = ROOT_DIR / powerbi_dir
            if candidate.exists():
                powerbi_dir = str(candidate)

        df = cleaned_df.copy()

        # Rule-based Anomaly Scoring for incoming live stream
        def evaluate_anomaly(row):
            # Check extreme discount / margin glitch
            if row["DiscountRate"] >= 0.70 or row["ProfitMargin"] < -20.0:
                return 1, 0.95, "Critical Pricing Glitch & Margin Erosion"
            # Extreme volume
            elif row["Quantity"] >= 150:
                return 1, 0.90, "Extreme Bulk Volume Spike"
            # High value return
            elif row["IsReturned"] == 1 and row["NetRevenue"] > 10000:
                return 1, 0.88, "High-Exposure Fraudulent Return"
            # Supply chain cost surge
            elif row["CostPrice"] > row["UnitPrice"]:
                return 1, 0.85, "Supply Chain Cost Surge Outlier"
            return 0, 0.05, "Normal Transaction"

        scores = [evaluate_anomaly(row) for _, row in df.iterrows()]
        df["Anomaly_Flag"] = [s[0] for s in scores]
        df["Anomaly_Score"] = [s[1] for s in scores]
        df["Detected_Anomaly_Type"] = [s[2] for s in scores]

        # Compute DateKey
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        df["DateKey"] = df["TransactionDate"].dt.strftime("%Y%m%d").astype(int)
        df["TransactionDate"] = df["TransactionDate"].dt.strftime("%Y-%m-%d")

        # Map Channel to ChannelID
        channel_id_map = {
            "Direct Sales Enterprise": "CHN-01",
            "Digital Cloud Portal": "CHN-02",
            "Strategic Partner Reseller": "CHN-03",
            "EDI Automated Contract": "CHN-04"
        }
        df["ChannelID"] = df["Channel"].map(lambda c: channel_id_map.get(c, "CHN-02"))

        # Ingest into SQLite Warehouse
        conn = sqlite3.connect(self.db_path)
        try:
            # 1. Append to fact_transactions (avoid duplicate TransactionID)
            cursor = conn.cursor()
            existing_ids = set()
            try:
                cursor.execute("SELECT TransactionID FROM fact_transactions;")
                existing_ids = {r[0] for r in cursor.fetchall()}
            except Exception:
                pass

            # Filter out existing if any
            new_txns = df[~df["TransactionID"].isin(existing_ids)].copy()
            if not new_txns.empty:
                cols_to_insert = [
                    "TransactionID", "DateKey", "TransactionDate", "CustomerID", "ProductID",
                    "ChannelID", "Quantity", "UnitPrice", "CostPrice", "DiscountRate",
                    "GrossRevenue", "DiscountAmount", "NetRevenue", "TotalCost", "Profit",
                    "ProfitMargin", "PaymentMethod", "IsReturned", "Anomaly_Flag",
                    "Anomaly_Score", "Detected_Anomaly_Type"
                ]
                new_txns[cols_to_insert].to_sql("fact_transactions", conn, if_exists="append", index=False)

                # 2. Append to fact_anomalies if any flagged
                anom_records = new_txns[new_txns["Anomaly_Flag"] == 1].copy()
                if not anom_records.empty:
                    anom_cols = [
                        "TransactionID", "DateKey", "TransactionDate", "CustomerID", "ProductID",
                        "ChannelID", "Quantity", "NetRevenue", "DiscountRate", "Profit",
                        "ProfitMargin", "Anomaly_Score", "Detected_Anomaly_Type"
                    ]
                    anom_to_insert = anom_records[anom_cols].copy()
                    anom_to_insert["Investigation_Status"] = "Pending Live Investigation"
                    anom_to_insert.to_sql("fact_anomalies", conn, if_exists="append", index=False)

                # 3. Update dim_customer if new customer appears
                for _, row in new_txns.iterrows():
                    cursor.execute("SELECT CustomerID FROM dim_customer WHERE CustomerID = ?;", (row["CustomerID"],))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO dim_customer (CustomerID, CustomerName, CustomerSegment, Region, State, Recency, Frequency, Monetary, AvgOrderValue, AvgProfitMargin, ReturnCount, ReturnRate, Cluster, RFM_Segment, RFM_Score, ChurnRisk)
                            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, 1, 'Promising & Emerging Mid-Market', 333, 'Stable Active');
                        """, (
                            row["CustomerID"], row["CustomerName"], row["CustomerSegment"],
                            row["Region"], row["State"], row["NetRevenue"], row["NetRevenue"],
                            row["ProfitMargin"], row["IsReturned"], float(row["IsReturned"])
                        ))

                # 4. Update dim_product if new product appears
                for _, row in new_txns.iterrows():
                    cursor.execute("SELECT ProductID FROM dim_product WHERE ProductID = ?;", (row["ProductID"],))
                    if not cursor.fetchone():
                        margin_std = round(((row["UnitPrice"] - row["CostPrice"]) / row["UnitPrice"]) * 100, 2) if row["UnitPrice"] > 0 else 0.0
                        cursor.execute("""
                            INSERT INTO dim_product (ProductID, ProductName, Category, BasePrice, CostPrice, StandardMarginPercent)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (
                            row["ProductID"], row["ProductName"], row["Category"],
                            row["UnitPrice"], row["CostPrice"], margin_std
                        ))

                conn.commit()

            # Refresh Power BI Star-Schema CSVs
            try:
                for tbl in ["fact_transactions", "fact_anomalies", "dim_customer", "dim_product"]:
                    tdf = pd.read_sql_query(f"SELECT * FROM {tbl};", conn)
                    csv_path = os.path.join(powerbi_dir, f"{tbl}.csv")
                    tdf.to_csv(csv_path, index=False, encoding="utf-8")
            except Exception as e:
                print(f"[WARN] Ingestion: Power BI CSV sync warning ({e})")

            anom_count = int(new_txns["Anomaly_Flag"].sum()) if not new_txns.empty else 0
            rev_added = float(new_txns["NetRevenue"].sum()) if not new_txns.empty else 0.0

            return {
                "status": "success",
                "records_ingested": len(new_txns),
                "anomalies_detected": anom_count,
                "revenue_added": rev_added,
                "anomalous_records": new_txns[new_txns["Anomaly_Flag"] == 1][[
                    "TransactionID", "CustomerID", "ProductName", "NetRevenue", "Detected_Anomaly_Type"
                ]].to_dict(orient="records") if not new_txns.empty else []
            }
        finally:
            conn.close()

    def ingest_single_realtime_transaction(self, txn_dict: dict) -> dict:
        """Helper to validate, clean, score, and ingest a single real-time streaming transaction."""
        df_single = pd.DataFrame([txn_dict])
        cleaned_df, report = self.validate_and_clean(df_single, auto_impute=True)
        if report["errors"]:
            return {"status": "error", "message": "; ".join(report["errors"]), "details": report}

        res = self.score_and_ingest(cleaned_df)
        res["cleaned_record"] = cleaned_df.iloc[0].to_dict()
        return res
