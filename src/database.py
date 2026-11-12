"""
InsightAgent - Enterprise Data Warehouse & Star-Schema Pipeline
Transforms raw transactional and analytics data into an enterprise Star Schema,
loads tables into a local SQLite Data Warehouse, and exports clean CSVs for Power BI Desktop.
"""

import os
import sqlite3
import pandas as pd


class EnterpriseWarehouse:
    """
    Manages the SQLite Enterprise Data Warehouse (data/warehouse.db)
    and automated CSV exports for Power BI Desktop integration.
    """

    def __init__(
        self,
        db_path: str = "data/warehouse.db",
        powerbi_dir: str = "data/powerbi_exports"
    ):
        self.db_path = db_path
        self.powerbi_dir = powerbi_dir
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.powerbi_dir, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Returns a connection to the SQLite database with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def build_star_schema(
        self,
        scored_txns_df: pd.DataFrame,
        rfm_df: pd.DataFrame,
        rfm_summary_df: pd.DataFrame,
        anomalies_df: pd.DataFrame,
        forecast_df: pd.DataFrame
    ) -> dict[str, pd.DataFrame]:
        """
        Transforms flat transaction records and ML outputs into a dimensional Star Schema:
        - dim_date
        - dim_customer
        - dim_product
        - dim_channel
        - fact_transactions
        - fact_anomalies
        - fact_forecasts
        - fact_rfm_segments
        """
        print("[*] Enterprise Warehouse: Constructing Star-Schema Dimensional Model...")
        df = scored_txns_df.copy()
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        df["DateKey"] = df["TransactionDate"].dt.strftime("%Y%m%d").astype(int)

        # 1. Dimension: Date (dim_date)
        all_dates = pd.date_range(
            start=df["TransactionDate"].min(),
            end=max(df["TransactionDate"].max(), pd.to_datetime(forecast_df["ForecastDate"].max()))
        )
        dim_date = pd.DataFrame({
            "DateKey": all_dates.strftime("%Y%m%d").astype(int),
            "FullDate": all_dates.strftime("%Y-%m-%d"),
            "Year": all_dates.year,
            "Quarter": all_dates.quarter,
            "QuarterName": "Q" + all_dates.quarter.astype(str),
            "Month": all_dates.month,
            "MonthName": all_dates.strftime("%B"),
            "MonthShort": all_dates.strftime("%b"),
            "Day": all_dates.day,
            "DayOfWeek": all_dates.dayofweek + 1,  # 1=Monday, 7=Sunday
            "DayName": all_dates.strftime("%A"),
            "IsWeekend": all_dates.dayofweek.isin([5, 6]).astype(int),
            "WeekOfYear": all_dates.isocalendar().week.astype(int)
        })

        # 2. Dimension: Customer (dim_customer)
        dim_customer = rfm_df.copy()
        if "LastPurchaseDate" in dim_customer.columns:
            dim_customer["LastPurchaseDate"] = pd.to_datetime(dim_customer["LastPurchaseDate"]).dt.strftime("%Y-%m-%d")

        # 3. Dimension: Product (dim_product)
        dim_product = df.groupby("ProductID").agg(
            ProductName=("ProductName", "first"),
            Category=("Category", "first"),
            BasePrice=("UnitPrice", "first"),
            CostPrice=("CostPrice", "first")
        ).reset_index()
        dim_product["StandardMarginPercent"] = (
            ((dim_product["BasePrice"] - dim_product["CostPrice"]) / dim_product["BasePrice"]) * 100
        ).round(2)

        # 4. Dimension: Channel (dim_channel)
        unique_channels = df["Channel"].unique()
        dim_channel = pd.DataFrame({
            "ChannelID": [f"CHN-{i+1:02d}" for i in range(len(unique_channels))],
            "ChannelName": unique_channels,
            "ChannelType": ["Direct" if "Direct" in c else "Digital" if "Digital" in c else "Partner" for c in unique_channels]
        })
        channel_id_map = dict(zip(dim_channel["ChannelName"], dim_channel["ChannelID"]))
        df["ChannelID"] = df["Channel"].map(channel_id_map)

        # 5. Fact: Transactions (fact_transactions)
        fact_transactions = df[[
            "TransactionID", "DateKey", "TransactionDate", "CustomerID", "ProductID",
            "ChannelID", "Quantity", "UnitPrice", "CostPrice", "DiscountRate",
            "GrossRevenue", "DiscountAmount", "NetRevenue", "TotalCost", "Profit",
            "ProfitMargin", "PaymentMethod", "IsReturned", "Anomaly_Flag",
            "Anomaly_Score", "Detected_Anomaly_Type"
        ]].copy()

        # 6. Fact: Anomalies (fact_anomalies)
        anom_copy = anomalies_df.copy()
        anom_copy["TransactionDate"] = pd.to_datetime(anom_copy["TransactionDate"])
        anom_copy["DateKey"] = anom_copy["TransactionDate"].dt.strftime("%Y%m%d").astype(int)
        anom_copy["ChannelID"] = anom_copy["Channel"].map(channel_id_map)
        anom_copy["Investigation_Status"] = "Pending AI Review"

        fact_anomalies = anom_copy[[
            "TransactionID", "DateKey", "TransactionDate", "CustomerID", "ProductID",
            "ChannelID", "Quantity", "NetRevenue", "DiscountRate", "Profit",
            "ProfitMargin", "Anomaly_Score", "Detected_Anomaly_Type", "Investigation_Status"
        ]].copy()

        # 7. Fact: Forecasts (fact_forecasts)
        f_copy = forecast_df.copy()
        f_copy["DateKey"] = pd.to_datetime(f_copy["ForecastDate"]).dt.strftime("%Y%m%d").astype(int)
        fact_forecasts = f_copy[[
            "DateKey", "ForecastDate", "DayOfWeek", "ForecastedRevenue",
            "LowerBound", "UpperBound", "ModelType"
        ]].copy()

        # 8. Fact: RFM Segments Summary (fact_rfm_segments)
        fact_rfm_segments = rfm_summary_df.copy()

        star_tables = {
            "dim_date": dim_date,
            "dim_customer": dim_customer,
            "dim_product": dim_product,
            "dim_channel": dim_channel,
            "fact_transactions": fact_transactions,
            "fact_anomalies": fact_anomalies,
            "fact_forecasts": fact_forecasts,
            "fact_rfm_segments": fact_rfm_segments
        }

        return star_tables

    def load_warehouse(self, star_tables: dict[str, pd.DataFrame]) -> None:
        """
        Loads all star schema tables into SQLite and builds analytical indices.
        """
        print(f"[*] Enterprise Warehouse: Loading tables into SQLite warehouse at {self.db_path}...")
        conn = sqlite3.connect(self.db_path)
        
        for table_name, table_df in star_tables.items():
            table_df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"  [+] Loaded '{table_name}': {len(table_df):,} rows")

        # Create indexes for high-speed BI querying
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON fact_transactions(DateKey);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_cust ON fact_transactions(CustomerID);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_prod ON fact_transactions(ProductID);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_anom ON fact_transactions(Anomaly_Flag);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_key ON dim_date(DateKey);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_id ON dim_customer(CustomerID);")
        conn.commit()
        conn.close()
        print(f"[SUCCESS] SQLite Enterprise Warehouse successfully populated.")

    def export_powerbi_csvs(self, star_tables: dict[str, pd.DataFrame]) -> list[str]:
        """
        Exports all dimensional tables as individual CSV files into data/powerbi_exports/
        for seamless Power BI Desktop Get-Data ingestion.
        """
        print(f"[*] Enterprise Warehouse: Exporting clean Star-Schema CSVs to {self.powerbi_dir}...")
        exported_paths = []
        
        for table_name, table_df in star_tables.items():
            csv_path = os.path.join(self.powerbi_dir, f"{table_name}.csv")
            table_df.to_csv(csv_path, index=False, encoding="utf-8")
            exported_paths.append(csv_path)
            print(f"  [+] Exported: {csv_path} ({len(table_df):,} records)")

        print(f"[SUCCESS] Exported {len(exported_paths)} Power BI Star-Schema CSV files.")
        return exported_paths
