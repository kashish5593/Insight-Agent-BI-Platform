"""
InsightAgent - Autonomous Natural Language to SQL (NLQ-to-SQL) Agent
Converts natural language analytical questions into safe, optimized SQLite queries,
executes them against the Enterprise Warehouse, and synthesizes executive answers.
"""

import os
import re
import sqlite3
from pathlib import Path
import pandas as pd
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

try:
    from google import genai
except ImportError:
    genai = None


def safe_to_markdown(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)


class NLQSQLAgent:
    """
    Translates natural language questions into verified read-only SQL,
    executes against SQLite warehouse, and generates executive summaries.
    """

    DATABASE_SCHEMA = """
Database Schema (SQLite Star-Schema Enterprise Warehouse):

1. dim_customer:
   - CustomerID (TEXT PRIMARY KEY)
   - CustomerName (TEXT)
   - CustomerSegment (TEXT) -- 'Enterprise Tier 1', 'Strategic Mid-Market', 'Emerging SMB', 'Government & Edu'
   - Region (TEXT) -- 'North America - East', 'North America - West', 'North America - Midwest', 'North America - South', 'EMEA - Western Europe', 'APAC - Regional'
   - State (TEXT)
   - Recency (INTEGER) -- Days since last order
   - Frequency (INTEGER) -- Total orders
   - Monetary (REAL) -- Total spend
   - AvgOrderValue (REAL)
   - AvgProfitMargin (REAL)
   - RFM_Segment (TEXT) -- 'Champions & High-Value Strategic', 'Loyal Core Growth Accounts', 'Promising & Emerging Mid-Market', 'At-Risk & Hibernating Accounts'
   - ChurnRisk (TEXT) -- 'Critical High Risk', 'Medium At-Risk', 'Stable Active', 'Low Risk (Champion)'

2. dim_product:
   - ProductID (TEXT PRIMARY KEY)
   - ProductName (TEXT)
   - Category (TEXT) -- 'Cloud Infrastructure', 'AI & Analytics', 'Cybersecurity', 'Enterprise Hardware', 'Consulting & Support'
   - BasePrice (REAL)
   - CostPrice (REAL)
   - StandardMarginPercent (REAL)

3. dim_channel:
   - ChannelID (TEXT PRIMARY KEY)
   - ChannelName (TEXT) -- 'Direct Sales Enterprise', 'Digital Cloud Portal', 'Strategic Partner Reseller', 'EDI Automated Contract'
   - ChannelType (TEXT)

4. dim_date:
   - DateKey (INTEGER PRIMARY KEY) -- YYYYMMDD
   - FullDate (TEXT) -- YYYY-MM-DD
   - Year (INTEGER)
   - Quarter (INTEGER)
   - QuarterName (TEXT) -- 'Q1', 'Q2', etc.
   - Month (INTEGER)
   - MonthName (TEXT)
   - MonthShort (TEXT)
   - Day (INTEGER)
   - DayOfWeek (INTEGER)
   - DayName (TEXT)
   - IsWeekend (INTEGER)

5. fact_transactions:
   - TransactionID (TEXT PRIMARY KEY)
   - DateKey (INTEGER)
   - TransactionDate (TEXT)
   - CustomerID (TEXT)
   - ProductID (TEXT)
   - ChannelID (TEXT)
   - Quantity (INTEGER)
   - UnitPrice (REAL)
   - CostPrice (REAL)
   - DiscountRate (REAL)
   - GrossRevenue (REAL)
   - DiscountAmount (REAL)
   - NetRevenue (REAL)
   - TotalCost (REAL)
   - Profit (REAL)
   - ProfitMargin (REAL)
   - PaymentMethod (TEXT)
   - IsReturned (INTEGER) -- 0 or 1
   - Anomaly_Flag (INTEGER) -- 1 if anomaly, 0 otherwise
   - Anomaly_Score (REAL)
   - Detected_Anomaly_Type (TEXT)

6. fact_anomalies:
   - TransactionID (TEXT)
   - DateKey (INTEGER)
   - TransactionDate (TEXT)
   - CustomerID (TEXT)
   - ProductID (TEXT)
   - ChannelID (TEXT)
   - Quantity (INTEGER)
   - NetRevenue (REAL)
   - DiscountRate (REAL)
   - Profit (REAL)
   - ProfitMargin (REAL)
   - Anomaly_Score (REAL)
   - Detected_Anomaly_Type (TEXT)
   - Investigation_Status (TEXT)

7. fact_forecasts:
   - DateKey (INTEGER)
   - ForecastDate (TEXT)
   - DayOfWeek (TEXT)
   - ForecastedRevenue (REAL)
   - LowerBound (REAL)
   - UpperBound (REAL)
   - ModelType (TEXT)

8. fact_rfm_segments:
   - RFM_Segment (TEXT)
   - CustomerCount (INTEGER)
   - TotalRevenue (REAL)
   - AvgRevenuePerCustomer (REAL)
   - AvgFrequency (REAL)
   - AvgRecencyDays (REAL)
   - AvgMarginPercent (REAL)
   - RevenueSharePct (REAL)
"""

    DISALLOWED_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE",
        "REPLACE", "EXEC", "EXECUTE", "PRAGMA", "ATTACH", "DETACH"
    ]

    def __init__(self, db_path: str = "data/warehouse.db"):
        if not os.path.isabs(db_path) and not os.path.exists(db_path):
            candidate = ROOT_DIR / db_path
            if candidate.exists():
                db_path = str(candidate)
        self.db_path = db_path
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self.model_name = "gemini-2.5-flash"
        
        if self.api_key and self.api_key != "your_gemini_api_key_here" and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[WARN] NLQSQLAgent: Gemini client init error ({e}). Using Heuristic SQL engine.")
                self.client = None

    def validate_sql(self, sql_query: str) -> tuple[bool, str]:
        """Ensures that SQL query is safe, read-only, and free of injection risks."""
        cleaned = sql_query.strip().strip(";").strip()
        
        # Check forbidden mutation keywords
        tokens = re.findall(r"\b[A-Za-z]+\b", cleaned.upper())
        for token in tokens:
            if token in self.DISALLOWED_KEYWORDS:
                return False, f"Prohibited mutation keyword detected: '{token}'. Only read-only SELECT queries are allowed."

        # Must start with SELECT or WITH
        if not (cleaned.upper().startswith("SELECT") or cleaned.upper().startswith("WITH")):
            return False, "Query must begin with SELECT or WITH."

        # Check for multiple statements separated by semicolon
        if ";" in cleaned:
            return False, "Multiple SQL statements are not permitted."

        return True, cleaned

    def execute_query(self, sql_query: str) -> pd.DataFrame:
        """Executes validated SQL query against SQLite warehouse and returns a DataFrame."""
        is_valid, sanitized_or_msg = self.validate_sql(sql_query)
        if not is_valid:
            raise ValueError(sanitized_or_msg)

        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql_query(sanitized_or_msg, conn)
            return df
        finally:
            conn.close()

    def ask(self, user_question: str) -> dict[str, Any]:
        """
        End-to-end question answering pipeline:
        1. Translates natural language question to SQL
        2. Executes SQL against SQLite data warehouse
        3. Formulates executive summary answer
        """
        user_question = user_question.strip()
        if not user_question:
            return {
                "question": "",
                "sql": "",
                "dataframe": pd.DataFrame(),
                "summary": "Please provide a valid business intelligence question.",
                "agent_mode": "None",
                "row_count": 0
            }

        # Step 1: Generate SQL Query
        sql_query, gen_mode = self._generate_sql(user_question)

        # Step 2: Execute SQL Query safely
        try:
            df_result = self.execute_query(sql_query)
        except Exception as query_err:
            print(f"[WARN] Generated SQL failed ({query_err}). Reverting to fallback heuristic SQL.")
            sql_query = self._heuristic_sql_fallback(user_question)
            try:
                df_result = self.execute_query(sql_query)
            except Exception as e:
                return {
                    "question": user_question,
                    "sql": sql_query,
                    "dataframe": pd.DataFrame(),
                    "summary": f"Query execution error: {str(e)}",
                    "agent_mode": gen_mode,
                    "row_count": 0
                }

        # Step 3: Generate Executive Summary
        summary = self._summarize_result(user_question, sql_query, df_result, gen_mode)

        return {
            "question": user_question,
            "sql": sql_query,
            "dataframe": df_result,
            "data": df_result.to_dict(orient="records"),
            "summary": summary,
            "agent_mode": gen_mode,
            "row_count": len(df_result)
        }

    def _generate_sql(self, question: str) -> tuple[str, str]:
        """Generates SQL using Gemini or Heuristic intent matching."""
        if self.client:
            prompt = f"""
You are an expert SQL Data Architect specializing in SQLite enterprise analytics.
Translate the user's analytical question into a SINGLE, highly optimized SQLite query.

{self.DATABASE_SCHEMA}

Rules:
1. Output ONLY the raw SQL query inside ```sql ... ``` block or plain text. No conversational chatter.
2. Only use read-only SELECT or WITH statements.
3. Use proper JOINs between fact_transactions, dim_customer, dim_product, dim_channel, dim_date.
4. Format monetary sums with ROUND(..., 2).
5. Limit results to 20 rows if querying detailed tables without aggregation.

User Question: "{question}"
"""
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                text = response.text.strip()
                # Extract SQL from markdown code block if present
                match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
                if match:
                    sql = match.group(1).strip()
                else:
                    sql = text.strip()
                # Clean up any trailing semicolon
                sql = sql.rstrip(";")
                return sql, "Gemini 2.5 Flash Autonomous NLQ-to-SQL"
            except Exception as e:
                print(f"[WARN] Gemini NLQ generation error ({e}). Activating Heuristic SQL Generator.")

        return self._heuristic_sql_fallback(question), "Autonomous Heuristic SQL Engine (Offline/Fallback)"

    def _heuristic_sql_fallback(self, question: str) -> str:
        """
        Pattern-matching SQL generator covering high-frequency business intelligence inquiries.
        """
        q = question.lower()

        # 1. Product & Category performance
        if "category" in q or "categories" in q:
            if "profit" in q or "margin" in q:
                return """
SELECT p.Category,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       ROUND(SUM(t.Profit), 2) AS TotalProfit,
       ROUND(AVG(t.ProfitMargin), 2) AS AvgMarginPct,
       COUNT(t.TransactionID) AS TransactionCount
FROM fact_transactions t
JOIN dim_product p ON t.ProductID = p.ProductID
GROUP BY p.Category
ORDER BY TotalProfit DESC;
""".strip()
            else:
                return """
SELECT p.Category,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       SUM(t.Quantity) AS TotalUnitsSold,
       COUNT(t.TransactionID) AS TransactionCount,
       ROUND(AVG(t.ProfitMargin), 2) AS AvgMarginPct
FROM fact_transactions t
JOIN dim_product p ON t.ProductID = p.ProductID
GROUP BY p.Category
ORDER BY TotalRevenue DESC;
""".strip()

        if "top product" in q or "best product" in q or "product" in q:
            return """
SELECT p.ProductName,
       p.Category,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       SUM(t.Quantity) AS UnitsSold,
       ROUND(SUM(t.Profit), 2) AS TotalProfit
FROM fact_transactions t
JOIN dim_product p ON t.ProductID = p.ProductID
GROUP BY p.ProductID, p.ProductName, p.Category
ORDER BY TotalRevenue DESC
LIMIT 10;
""".strip()

        # 2. Regional / Geographic performance
        if "region" in q or "state" in q or "west" in q or "east" in q or "midwest" in q or "south" in q:
            return """
SELECT c.Region,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       ROUND(SUM(t.Profit), 2) AS TotalProfit,
       COUNT(DISTINCT c.CustomerID) AS CustomerCount,
       ROUND(AVG(t.ProfitMargin), 2) AS AvgMarginPct
FROM fact_transactions t
JOIN dim_customer c ON t.CustomerID = c.CustomerID
GROUP BY c.Region
ORDER BY TotalRevenue DESC;
""".strip()

        # 3. Customer Segments / RFM
        if "segment" in q or "rfm" in q or "champion" in q or "risk" in q or "customer" in q:
            return """
SELECT RFM_Segment,
       CustomerCount,
       TotalRevenue,
       AvgRevenuePerCustomer,
       AvgFrequency,
       AvgRecencyDays,
       RevenueSharePct
FROM fact_rfm_segments
ORDER BY TotalRevenue DESC;
""".strip()

        # 4. Anomalies / Pricing Glitches / Fraud
        if "anomal" in q or "glitch" in q or "fraud" in q or "loss" in q or "spike" in q:
            return """
SELECT Detected_Anomaly_Type,
       COUNT(*) AS AnomalyCount,
       ROUND(SUM(NetRevenue), 2) AS RevenueExposed,
       ROUND(SUM(Profit), 2) AS TotalProfitImpact,
       ROUND(AVG(DiscountRate) * 100, 1) AS AvgDiscountPct
FROM fact_anomalies
GROUP BY Detected_Anomaly_Type
ORDER BY AnomalyCount DESC;
""".strip()

        # 5. Channel performance
        if "channel" in q or "online" in q or "portal" in q or "direct" in q:
            return """
SELECT ch.ChannelName,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       ROUND(SUM(t.Profit), 2) AS TotalProfit,
       COUNT(t.TransactionID) AS OrderCount
FROM fact_transactions t
JOIN dim_channel ch ON t.ChannelID = ch.ChannelID
GROUP BY ch.ChannelName
ORDER BY TotalRevenue DESC;
""".strip()

        # 6. Forecasts
        if "forecast" in q or "predict" in q or "future" in q or "next month" in q:
            return """
SELECT ForecastDate,
       DayOfWeek,
       ForecastedRevenue,
       LowerBound,
       UpperBound,
       ModelType
FROM fact_forecasts
ORDER BY ForecastDate ASC
LIMIT 14;
""".strip()

        # Default: Executive KPI Monthly Revenue Trend
        return """
SELECT d.Year,
       d.MonthName,
       ROUND(SUM(t.NetRevenue), 2) AS TotalRevenue,
       ROUND(SUM(t.Profit), 2) AS TotalProfit,
       COUNT(t.TransactionID) AS TransactionCount
FROM fact_transactions t
JOIN dim_date d ON t.DateKey = d.DateKey
GROUP BY d.Year, d.Month, d.MonthName
ORDER BY d.Year DESC, d.Month DESC
LIMIT 12;
""".strip()

    def _summarize_result(
        self,
        question: str,
        sql_query: str,
        df_result: pd.DataFrame,
        mode: str
    ) -> str:
        """Generates clear, executive natural language insights from query results."""
        if df_result.empty:
            return "The database query executed successfully, but returned 0 matching records."

        if self.client and "Gemini" in mode:
            sample_data = safe_to_markdown(df_result.head(10))
            prompt = f"""
You are an executive Chief Analytics Officer. The user asked: "{question}"
The database executed the following query:
`{sql_query}`

Data Result:
{sample_data}

Provide a concise, 2-to-3 paragraph executive summary answering the question directly with key figures, highlights, and any notable strategic implications. Use markdown formatting.
"""
            try:
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return resp.text
            except Exception as e:
                print(f"[WARN] Gemini summary generation error ({e}). Using Heuristic summary.")

        # Heuristic Summary
        rows = len(df_result)
        cols = list(df_result.columns)
        first_row = df_result.iloc[0].to_dict()
        
        summary = f"### 📊 Analytical Findings ({rows} records retrieved)\n\n"
        summary += f"Based on the enterprise data warehouse query for **'{question}'**:\n\n"

        # Highlight top record
        key_name = list(first_row.keys())[0]
        val_name = first_row[key_name]
        summary += f"- **Top Performer / Primary Focus:** `{key_name}: {val_name}`"
        
        if "TotalRevenue" in first_row:
            summary += f" generated **${first_row['TotalRevenue']:,.2f}** in net revenue"
        if "TotalProfit" in first_row:
            summary += f" with **${first_row['TotalProfit']:,.2f}** in net profit"
        if "AvgMarginPct" in first_row:
            summary += f" ({first_row['AvgMarginPct']}% margin)"
        summary += ".\n"

        # Summary statistics
        if "TotalRevenue" in df_result.columns:
            tot_rev = df_result["TotalRevenue"].sum()
            summary += f"- **Cumulative Segment Revenue:** **${tot_rev:,.2f}** across all returned records.\n"
        if "TotalProfit" in df_result.columns:
            tot_prof = df_result["TotalProfit"].sum()
            summary += f"- **Cumulative Profit Contribution:** **${tot_prof:,.2f}**.\n"
        if "AnomalyCount" in df_result.columns:
            tot_anom = df_result["AnomalyCount"].sum()
            summary += f"- **Identified Anomaly Incidents:** **{tot_anom:,}** operational events.\n"

        summary += f"\n*Generated by InsightAgent NLQ Subsystem ({mode})*"
        return summary
