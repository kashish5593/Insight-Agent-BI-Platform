"""
InsightAgent - Automated Test & Verification Suite
Verifies data pipeline, machine learning, agents, and FastAPI endpoints.
"""

import sys
import unittest
import pandas as pd
from fastapi.testclient import TestClient

from src.agents.anomaly_agent import AnomalyAgent
from src.agents.nlq_sql_agent import NLQSQLAgent
from src.agents.executive_agent import ExecutiveAgent
from src.api.main import app


class TestInsightAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 60)
        print("  RUNNING INSIGHTAGENT INTEGRATION & UNIT TESTS")
        print("=" * 60)

    def test_01_anomaly_agent(self):
        print("\n[TEST] 1. Anomaly Detective Agent...")
        agent = AnomalyAgent()
        res = agent.run_diagnosis()
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["metrics"]["anomaly_count"], 0)
        self.assertIn("diagnosis_markdown", res)
        print(f"  [PASS] Anomaly Agent operating in mode: {res['agent_mode']}")
        print(f"  [PASS] Isolated {res['metrics']['anomaly_count']} anomalies (${res['metrics']['total_revenue_exposed']:,.2f} exposed)")

    def test_02_nlq_sql_agent(self):
        print("\n[TEST] 2. Conversational NLQ-to-SQL Agent...")
        agent = NLQSQLAgent()
        queries = [
            "What is our revenue and profit by category?",
            "Show me top 5 products by revenue",
            "What is the breakdown of anomalies by type?"
        ]
        for q in queries:
            res = agent.ask(q)
            self.assertGreater(res["row_count"], 0)
            self.assertIn("SELECT", res["sql"].upper())
            self.assertTrue(len(res["summary"]) > 20)
            print(f"  [PASS] Query: '{q}' -> Returned {res['row_count']} rows via {res['agent_mode']}")

    def test_03_executive_agent(self):
        print("\n[TEST] 3. Executive CAO Agent...")
        agent = ExecutiveAgent()
        res = agent.generate_briefing()
        self.assertIn("briefing_markdown", res)
        self.assertGreater(len(res["briefing_markdown"]), 100)
        kpis = res["telemetry"]["kpis"]
        self.assertGreater(kpis["TotalNetRevenue"], 0)
        print(f"  [PASS] Executive Briefing generated via: {res['agent_mode']}")
        print(f"  [PASS] Corporate Net Revenue: ${kpis['TotalNetRevenue']:,.2f}")

    def test_04_fastapi_endpoints(self):
        print("\n[TEST] 4. FastAPI Endpoints via TestClient...")
        client = TestClient(app)

        # Health
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["database_connected"])

        # Summary KPIs
        resp = client.get("/api/metrics/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertGreater(data["TotalRevenue"], 0)

        # Anomalies
        resp = client.get("/api/anomalies?limit=10")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["anomalies"]), 1)

        # Segments
        resp = client.get("/api/segments")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["segments"]), 4)

        # Forecast
        resp = client.get("/api/forecast")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["forecast_days"], 30)

        # Chat endpoint
        resp = client.post("/api/agents/chat", json={"question": "What are our top products?"})
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json()["row_count"], 0)

        # Diagnose anomalies endpoint
        resp = client.post("/api/agents/diagnose-anomalies", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("diagnosis_markdown", resp.json())

        # Executive briefing endpoint
        resp = client.post("/api/agents/executive-briefing")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("briefing_markdown", resp.json())

        print("  [PASS] All 8 FastAPI REST endpoints responded with HTTP 200 OK")

    def test_05_data_ingestion_and_cleaning(self):
        print("\n[TEST] 5. Data Ingestion, Cleaning & Real-Time Streaming...")
        from src.data_ingestion import DataIngestionEngine
        import io

        engine = DataIngestionEngine()

        # 5.1 Test automated cleaning on dirty data
        dirty_data = pd.DataFrame([
            {
                "TransactionID": "TXN-TEST-001",
                "CustomerID": "CUST-9999",
                "ProductID": "PRD-101",
                "Quantity": -5,          # Should be clipped to 1
                "UnitPrice": 1000.0,
                "DiscountRate": 15,      # Should be normalized to 0.15
                "CostPrice": None        # Should be auto-imputed
            },
            {
                "TransactionID": "TXN-TEST-001",  # Duplicate ID
                "CustomerID": "CUST-9999",
                "ProductID": "PRD-101",
                "Quantity": 2,
                "UnitPrice": 1000.0
            }
        ])

        cleaned_df, report = engine.validate_and_clean(dirty_data, auto_impute=True, remove_duplicates=True)
        self.assertEqual(report["cleaned_rows"], 1)
        self.assertEqual(report["duplicates_removed"], 1)
        self.assertEqual(cleaned_df.iloc[0]["Quantity"], 1)
        self.assertAlmostEqual(cleaned_df.iloc[0]["DiscountRate"], 0.15)
        self.assertGreater(cleaned_df.iloc[0]["CostPrice"], 0)
        self.assertIn("NetRevenue", cleaned_df.columns)
        self.assertIn("ProfitMargin", cleaned_df.columns)
        print("  [PASS] Data Cleaning Engine correctly deduplicated, clipped bounds & imputed financials.")

        # 5.2 Test FastAPI Ingestion Endpoints
        client = TestClient(app)

        # Template endpoint
        resp = client.get("/api/data/schema-template")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("schema_specification", resp.json())
        print("  [PASS] GET /api/data/schema-template responded 200 OK.")

        # Real-time single transaction endpoint
        rt_payload = {
            "CustomerID": "CUST-8888",
            "ProductID": "PRD-201",
            "Quantity": 5,
            "UnitPrice": 480.0,
            "DiscountRate": 0.05
        }
        resp = client.post("/api/data/ingest-realtime", json=rt_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "success")
        self.assertEqual(resp.json()["records_ingested"], 1)
        print("  [PASS] POST /api/data/ingest-realtime ingested and scored 1 live streaming record.")

        # Batch CSV upload endpoint
        sample_csv = "CustomerID,ProductID,Quantity,UnitPrice,DiscountRate\nCUST-7777,PRD-102,10,680.0,0.10\n"
        files = {"file": ("batch_test.csv", io.BytesIO(sample_csv.encode("utf-8")), "text/csv")}
        resp = client.post("/api/data/upload-batch", files=files)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "success")
        self.assertEqual(resp.json()["records_ingested"], 1)
        print("  [PASS] POST /api/data/upload-batch parsed, cleaned, and ingested batch CSV.")


if __name__ == "__main__":
    unittest.main()
