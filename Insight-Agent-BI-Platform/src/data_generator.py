"""
InsightAgent - Enterprise Data Generator
Generates 10,000+ rows of realistic multi-channel enterprise retail & SaaS transactions
with injected statistical and operational anomalies.
"""

import os
import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


def generate_enterprise_dataset(
    num_rows: int = 12000,
    random_seed: int = 42,
    output_path: str = "data/raw/enterprise_transactions_raw.csv"
) -> pd.DataFrame:
    """
    Generates synthetic enterprise data with realistic seasonal distributions,
    customer segments, product catalogs, and injected operational anomalies.
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    print(f"[*] Initiating Enterprise Data Generator: Targeting {num_rows:,} records...")

    # 1. Product Catalog Definitions
    categories_catalog = {
        "Cloud Infrastructure": [
            ("PRD-101", "Enterprise Cloud Compute Node (64 vCPU)", 1250.00, 520.00),
            ("PRD-102", "High-Throughput NVMe Storage (10TB)", 680.00, 240.00),
            ("PRD-103", "Managed Kubernetes Cluster Control Plane", 890.00, 310.00),
            ("PRD-104", "Dedicated VPC Peering Gateway", 450.00, 120.00),
        ],
        "AI & Analytics": [
            ("PRD-201", "InsightAgent Autonomous Intelligence Seat", 480.00, 110.00),
            ("PRD-202", "Enterprise LLM Inference Pipeline (Tier 1)", 1850.00, 680.00),
            ("PRD-203", "Real-Time Data Streaming Orchestrator", 950.00, 340.00),
            ("PRD-204", "Predictive Analytics Automated SDK", 720.00, 210.00),
        ],
        "Cybersecurity": [
            ("PRD-301", "Zero-Trust Endpoint Protection Suite", 350.00, 95.00),
            ("PRD-302", "NextGen Cloud Web Application Firewall", 1150.00, 380.00),
            ("PRD-303", "Automated Threat Hunting & SIEM License", 1450.00, 510.00),
            ("PRD-304", "Identity & Access Governance Hub", 620.00, 180.00),
        ],
        "Enterprise Hardware": [
            ("PRD-401", "Rackmount Deep Learning Server Node", 4800.00, 2900.00),
            ("PRD-402", "Enterprise 100GbE Managed Switch", 2200.00, 1100.00),
            ("PRD-403", "Edge AI Micro-Server Gateway", 1650.00, 850.00),
            ("PRD-404", "Dual Redundant Enterprise Power Unit", 520.00, 210.00),
        ],
        "Consulting & Support": [
            ("PRD-501", "24/7 Mission-Critical SLA Support", 2500.00, 950.00),
            ("PRD-502", "Cloud Architecture Migration Advisory", 3800.00, 1400.00),
            ("PRD-503", "Security Audit & Pen-Testing Sprint", 4200.00, 1600.00),
            ("PRD-504", "Executive AI Transformation Workshop", 5000.00, 1800.00),
        ]
    }

    all_products = []
    for cat, prods in categories_catalog.items():
        for pid, pname, bprice, cprice in prods:
            all_products.append({
                "ProductID": pid,
                "ProductName": pname,
                "Category": cat,
                "BasePrice": bprice,
                "CostPrice": cprice
            })
    products_df = pd.DataFrame(all_products)

    # 2. Customer Pool Generation (850 realistic corporate accounts)
    customer_prefixes = [
        "Apex", "Nexus", "Vertex", "Quantum", "Synergy", "Omni", "Vanguard",
        "Aegis", "Horizon", "Pinnacle", "Acro", "Starlight", "Core", "Global",
        "Cyber", "Pulse", "Titan", "Stratum", "Solstice", "Infiniti"
    ]
    customer_suffixes = [
        "Tech", "Systems", "Solutions", "Enterprises", "Logistics", "Financial",
        "Health", "Aerospace", "Energy", "Analytics", "Networks", "Labs", "Digital"
    ]
    regions_and_states = [
        ("North America - East", ["New York", "Massachusetts", "Virginia", "Pennsylvania", "Florida"]),
        ("North America - West", ["California", "Washington", "Oregon", "Nevada", "Arizona"]),
        ("North America - Midwest", ["Illinois", "Ohio", "Michigan", "Minnesota", "Indiana"]),
        ("North America - South", ["Texas", "Georgia", "North Carolina", "Tennessee"]),
        ("EMEA - Western Europe", ["United Kingdom", "Germany", "France", "Netherlands", "Switzerland"]),
        ("APAC - Regional", ["Singapore", "Japan", "Australia", "India"])
    ]
    segments = ["Enterprise Tier 1", "Strategic Mid-Market", "Emerging SMB", "Government & Edu"]

    num_customers = 850
    customers = []
    for i in range(1, num_customers + 1):
        c_id = f"CUST-{i:04d}"
        c_name = f"{random.choice(customer_prefixes)} {random.choice(customer_suffixes)} {random.choice(['Inc.', 'Corp.', 'LLC', 'Holdings'])}"
        reg_info = random.choice(regions_and_states)
        region = reg_info[0]
        state = random.choice(reg_info[1])
        segment = np.random.choice(segments, p=[0.20, 0.40, 0.30, 0.10])
        customers.append({
            "CustomerID": c_id,
            "CustomerName": c_name,
            "CustomerSegment": segment,
            "Region": region,
            "State": state
        })
    customers_df = pd.DataFrame(customers)

    # 3. Transaction Timing and Channels
    channels = ["Direct Sales Enterprise", "Digital Cloud Portal", "Strategic Partner Reseller", "EDI Automated Contract"]
    payment_methods = ["Corporate Net-30", "Corporate Net-60", "Wire Transfer", "Enterprise Credit Line"]

    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 6, 30)
    total_days = (end_date - start_date).days

    records = []
    for i in range(1, num_rows + 1):
        txn_id = f"TXN-{i:06d}"

        # Date modeling with mild upward growth trend & monthly seasonality
        day_offset = int(np.random.beta(2.2, 1.8) * total_days)
        txn_date = start_date + timedelta(days=day_offset)
        
        # Select customer & product
        cust = customers_df.iloc[random.randint(0, num_customers - 1)]
        prod = products_df.iloc[random.randint(0, len(products_df) - 1)]

        # Quantities based on segment
        if cust["CustomerSegment"] == "Enterprise Tier 1":
            qty = max(1, int(np.random.lognormal(mean=2.2, sigma=0.7)))
            channel = np.random.choice(channels, p=[0.55, 0.15, 0.20, 0.10])
        elif cust["CustomerSegment"] == "Strategic Mid-Market":
            qty = max(1, int(np.random.lognormal(mean=1.5, sigma=0.6)))
            channel = np.random.choice(channels, p=[0.30, 0.40, 0.20, 0.10])
        else:
            qty = max(1, int(np.random.lognormal(mean=0.9, sigma=0.5)))
            channel = np.random.choice(channels, p=[0.10, 0.65, 0.15, 0.10])

        qty = min(qty, 45)  # Cap normal maximum

        unit_price = float(prod["BasePrice"])
        cost_price = float(prod["CostPrice"])
        
        # Discount tier (0% to 22% normally)
        discount_rate = round(float(np.random.choice([0.0, 0.05, 0.10, 0.15, 0.20], p=[0.45, 0.25, 0.15, 0.10, 0.05])), 2)

        gross_rev = round(qty * unit_price, 2)
        disc_amt = round(gross_rev * discount_rate, 2)
        net_rev = round(gross_rev - disc_amt, 2)
        total_cost = round(qty * cost_price, 2)
        profit = round(net_rev - total_cost, 2)
        profit_margin = round((profit / net_rev) * 100, 2) if net_rev > 0 else 0.0
        
        is_returned = 1 if (random.random() < 0.022) else 0

        records.append({
            "TransactionID": txn_id,
            "TransactionDate": txn_date.strftime("%Y-%m-%d"),
            "CustomerID": cust["CustomerID"],
            "CustomerName": cust["CustomerName"],
            "CustomerSegment": cust["CustomerSegment"],
            "Region": cust["Region"],
            "State": cust["State"],
            "Channel": channel,
            "ProductID": prod["ProductID"],
            "ProductName": prod["ProductName"],
            "Category": prod["Category"],
            "UnitPrice": unit_price,
            "CostPrice": cost_price,
            "Quantity": qty,
            "DiscountRate": discount_rate,
            "GrossRevenue": gross_rev,
            "DiscountAmount": disc_amt,
            "NetRevenue": net_rev,
            "TotalCost": total_cost,
            "Profit": profit,
            "ProfitMargin": profit_margin,
            "PaymentMethod": random.choice(payment_methods),
            "IsReturned": is_returned,
            "True_Anomaly_Type": "Normal"
        })

    df = pd.DataFrame(records)

    # 4. Injected Realistic Operational Anomalies
    print("[*] Injecting realistic enterprise operational anomalies...")

    # Anomaly Type 1: System Pricing / Discount Glitch (e.g. ERP automated pricing rule error)
    # Effect: Severe margin erosion, discount 75%-90%, resulting in heavy negative profit
    glitch_indices = random.sample(range(len(df)), 45)
    for idx in glitch_indices:
        qty = df.loc[idx, "Quantity"]
        unit_p = df.loc[idx, "UnitPrice"]
        cost_p = df.loc[idx, "CostPrice"]
        err_discount = round(random.uniform(0.75, 0.90), 2)
        gross = round(qty * unit_p, 2)
        disc = round(gross * err_discount, 2)
        net = round(gross - disc, 2)
        tcost = round(qty * cost_p, 2)
        prof = round(net - tcost, 2)
        df.loc[idx, "DiscountRate"] = err_discount
        df.loc[idx, "DiscountAmount"] = disc
        df.loc[idx, "NetRevenue"] = net
        df.loc[idx, "Profit"] = prof
        df.loc[idx, "ProfitMargin"] = round((prof / net) * 100, 2) if net > 0 else -100.0
        df.loc[idx, "True_Anomaly_Type"] = "Pricing_Glitch_Margin_Erosion"

    # Anomaly Type 2: Cyber Monday / Flash Bulk Outlier (Massive quantity spikes)
    bulk_indices = random.sample(range(len(df)), 35)
    for idx in bulk_indices:
        huge_qty = random.randint(180, 450)
        unit_p = df.loc[idx, "UnitPrice"]
        cost_p = df.loc[idx, "CostPrice"]
        disc_rate = 0.25
        gross = round(huge_qty * unit_p, 2)
        disc = round(gross * disc_rate, 2)
        net = round(gross - disc, 2)
        tcost = round(huge_qty * cost_p, 2)
        prof = round(net - tcost, 2)
        df.loc[idx, "Quantity"] = huge_qty
        df.loc[idx, "DiscountRate"] = disc_rate
        df.loc[idx, "GrossRevenue"] = gross
        df.loc[idx, "DiscountAmount"] = disc
        df.loc[idx, "NetRevenue"] = net
        df.loc[idx, "TotalCost"] = tcost
        df.loc[idx, "Profit"] = prof
        df.loc[idx, "ProfitMargin"] = round((prof / net) * 100, 2)
        df.loc[idx, "True_Anomaly_Type"] = "Bulk_Spike_Outlier"

    # Anomaly Type 3: Fraudulent Return Rings (High order amount + immediate return)
    fraud_indices = random.sample(range(len(df)), 30)
    for idx in fraud_indices:
        huge_qty = random.randint(90, 160)
        unit_p = df.loc[idx, "UnitPrice"]
        cost_p = df.loc[idx, "CostPrice"]
        gross = round(huge_qty * unit_p, 2)
        disc = 0.0
        net = gross
        tcost = round(huge_qty * cost_p, 2)
        prof = round(net - tcost, 2)
        df.loc[idx, "Quantity"] = huge_qty
        df.loc[idx, "GrossRevenue"] = gross
        df.loc[idx, "DiscountRate"] = 0.0
        df.loc[idx, "DiscountAmount"] = disc
        df.loc[idx, "NetRevenue"] = net
        df.loc[idx, "TotalCost"] = tcost
        df.loc[idx, "Profit"] = prof
        df.loc[idx, "ProfitMargin"] = round((prof / net) * 100, 2)
        df.loc[idx, "IsReturned"] = 1
        df.loc[idx, "True_Anomaly_Type"] = "High_Value_Return_Fraud"

    # Anomaly Type 4: Vendor Supply Chain Surge (Component cost multiplied by 2.8x)
    cost_indices = random.sample(range(len(df)), 40)
    for idx in cost_indices:
        qty = df.loc[idx, "Quantity"]
        net = df.loc[idx, "NetRevenue"]
        elevated_cost = round(df.loc[idx, "CostPrice"] * random.uniform(2.6, 3.5), 2)
        tcost = round(qty * elevated_cost, 2)
        prof = round(net - tcost, 2)
        df.loc[idx, "CostPrice"] = elevated_cost
        df.loc[idx, "TotalCost"] = tcost
        df.loc[idx, "Profit"] = prof
        df.loc[idx, "ProfitMargin"] = round((prof / net) * 100, 2) if net > 0 else -100.0
        df.loc[idx, "True_Anomaly_Type"] = "Supply_Chain_Cost_Surge"

    # Sort chronological
    df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
    df = df.sort_values("TransactionDate").reset_index(drop=True)
    df["TransactionDate"] = df["TransactionDate"].dt.strftime("%Y-%m-%d")

    # Persist to disk
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[SUCCESS] Enterprise Dataset saved to {output_path} ({len(df):,} records, {len(df.columns)} columns).")
    
    return df


if __name__ == "__main__":
    generate_enterprise_dataset()
