"""
InsightAgent - Advanced Analytics & ML Engine
Implements:
1. RFM Customer Segmentation via K-Means Clustering & Quintile Scoring
2. Unsupervised Anomaly Detection via Isolation Forest
3. Time-Series Revenue Forecasting via Exponential Smoothing / State-Space Models
"""

import warnings
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")


class AnalyticsEngine:
    """
    Core Machine Learning and Statistical Modeling Engine for InsightAgent.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.kmeans_model = None
        self.isolation_forest = None

    def compute_rfm_segmentation(self, transactions_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Computes Recency, Frequency, Monetary (RFM) metrics for each customer,
        fits K-Means clustering, assigns business-grade segment labels,
        and computes segment summary aggregations.
        """
        print("[*] Analytics Engine: Computing Customer RFM Segmentation & K-Means Clusters...")
        df = transactions_df.copy()
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        reference_date = df["TransactionDate"].max() + pd.Timedelta(days=1)

        # Customer-level RFM Aggregation
        rfm = df.groupby("CustomerID").agg(
            CustomerName=("CustomerName", "first"),
            CustomerSegment=("CustomerSegment", "first"),
            Region=("Region", "first"),
            State=("State", "first"),
            LastPurchaseDate=("TransactionDate", "max"),
            Frequency=("TransactionID", "count"),
            Monetary=("NetRevenue", "sum"),
            AvgOrderValue=("NetRevenue", "mean"),
            AvgProfitMargin=("ProfitMargin", "mean"),
            ReturnCount=("IsReturned", "sum"),
        ).reset_index()

        rfm["Recency"] = (reference_date - rfm["LastPurchaseDate"]).dt.days
        rfm["ReturnRate"] = (rfm["ReturnCount"] / rfm["Frequency"]).round(4)
        rfm["Monetary"] = rfm["Monetary"].round(2)
        rfm["AvgOrderValue"] = rfm["AvgOrderValue"].round(2)
        rfm["AvgProfitMargin"] = rfm["AvgProfitMargin"].round(2)

        # Log transform to normalize skewed financial distributions
        rfm_features = pd.DataFrame()
        rfm_features["Recency_log"] = np.log1p(rfm["Recency"])
        rfm_features["Frequency_log"] = np.log1p(rfm["Frequency"])
        rfm_features["Monetary_log"] = np.log1p(np.maximum(rfm["Monetary"], 1.0))

        scaled_features = self.scaler.fit_transform(rfm_features)

        # K-Means Clustering (k=4 clusters)
        k = 4
        self.kmeans_model = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
        rfm["Cluster"] = self.kmeans_model.fit_predict(scaled_features)

        # Determine cluster semantics dynamically based on centroid Monetary & Frequency
        cluster_stats = rfm.groupby("Cluster").agg(
            mean_monetary=("Monetary", "mean"),
            mean_frequency=("Frequency", "mean"),
            mean_recency=("Recency", "mean")
        ).reset_index()

        # Sort clusters by value score (Monetary * 0.6 + Frequency * 0.4)
        cluster_stats["value_score"] = (
            (cluster_stats["mean_monetary"] / cluster_stats["mean_monetary"].max()) * 0.6 +
            (cluster_stats["mean_frequency"] / cluster_stats["mean_frequency"].max()) * 0.4
        )
        ranked_clusters = cluster_stats.sort_values(by="value_score", ascending=False)["Cluster"].tolist()

        cluster_name_map = {
            ranked_clusters[0]: "Champions & High-Value Strategic",
            ranked_clusters[1]: "Loyal Core Growth Accounts",
            ranked_clusters[2]: "Promising & Emerging Mid-Market",
            ranked_clusters[3]: "At-Risk & Hibernating Accounts"
        }
        rfm["RFM_Segment"] = rfm["Cluster"].map(cluster_name_map)

        # Quantile-based RFM Scoring (1 to 5)
        rfm["R_Score"] = pd.qcut(rfm["Recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
        rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        rfm["RFM_Score"] = rfm["R_Score"] * 100 + rfm["F_Score"] * 10 + rfm["M_Score"]

        # Churn Risk Classification
        def classify_churn_risk(row):
            if row["R_Score"] <= 2 and row["F_Score"] <= 2:
                return "Critical High Risk"
            elif row["R_Score"] <= 3:
                return "Medium At-Risk"
            elif row["R_Score"] >= 4 and row["M_Score"] >= 4:
                return "Low Risk (Champion)"
            return "Stable Active"

        rfm["ChurnRisk"] = rfm.apply(classify_churn_risk, axis=1)

        # Segment Summary Aggregation
        segment_summary = rfm.groupby("RFM_Segment").agg(
            CustomerCount=("CustomerID", "count"),
            TotalRevenue=("Monetary", "sum"),
            AvgRevenuePerCustomer=("Monetary", "mean"),
            AvgFrequency=("Frequency", "mean"),
            AvgRecencyDays=("Recency", "mean"),
            AvgMarginPercent=("AvgProfitMargin", "mean")
        ).reset_index().round(2)

        segment_summary["RevenueSharePct"] = (
            (segment_summary["TotalRevenue"] / segment_summary["TotalRevenue"].sum()) * 100
        ).round(2)

        print(f"[SUCCESS] RFM Segmentation Complete: {len(rfm):,} accounts segmented into 4 strategic tiers.")
        return rfm, segment_summary

    def detect_anomalies(self, transactions_df: pd.DataFrame, contamination: float = 0.015) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Applies Isolation Forest multidimensional unsupervised anomaly detection
        along with heuristic operational rules to classify root cause categories.
        """
        print("[*] Analytics Engine: Running Isolation Forest Anomaly Detection...")
        df = transactions_df.copy()

        # Multi-dimensional feature matrix for anomaly detection
        feature_cols = ["NetRevenue", "Quantity", "DiscountRate", "ProfitMargin", "CostPrice"]
        X = df[feature_cols].copy()
        
        # Impute any inf / nan values
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        self.isolation_forest = IsolationForest(
            n_estimators=120,
            contamination=contamination,
            random_state=self.random_state,
            n_jobs=-1
        )
        
        preds = self.isolation_forest.fit_predict(X_scaled)
        # -1 = anomaly, 1 = normal
        raw_scores = self.isolation_forest.decision_function(X_scaled)
        
        # Invert score so higher value = higher anomaly severity
        anomaly_scores = (raw_scores.max() - raw_scores) / (raw_scores.max() - raw_scores.min() + 1e-9)

        df["Anomaly_Flag"] = (preds == -1).astype(int)
        df["Anomaly_Score"] = np.round(anomaly_scores, 4)

        # Rule-based diagnostic categorization for business intelligence
        def diagnose_anomaly(row):
            if row["Anomaly_Flag"] == 0:
                return "Normal Transaction"
            
            # Diagnostic heuristics
            if row["DiscountRate"] >= 0.70 or row["ProfitMargin"] < -20.0:
                return "Critical Pricing Glitch & Margin Erosion"
            elif row["Quantity"] >= 150:
                return "Extreme Bulk Volume Spike"
            elif row["IsReturned"] == 1 and row["NetRevenue"] > 10000:
                return "High-Exposure Fraudulent Return"
            elif row["CostPrice"] > row["UnitPrice"]:
                return "Supply Chain Cost Surge Outlier"
            else:
                return "Multivariate Statistical Anomaly"

        df["Detected_Anomaly_Type"] = df.apply(diagnose_anomaly, axis=1)

        # Extract only anomaly records for detailed investigation
        anomalies_df = df[df["Anomaly_Flag"] == 1].sort_values(by="Anomaly_Score", ascending=False).reset_index(drop=True)

        print(f"[SUCCESS] Anomaly Detection Complete: Identified {len(anomalies_df):,} anomalies ({len(anomalies_df)/len(df)*100:.2f}% of transactions).")
        return df, anomalies_df

    def forecast_revenue(self, transactions_df: pd.DataFrame, forecast_horizon_days: int = 30) -> tuple[pd.DataFrame, dict]:
        """
        Aggregates daily enterprise revenue and computes a 30-day forecast with
        upper and lower confidence intervals using Holt-Winters Exponential Smoothing.
        """
        print(f"[*] Analytics Engine: Computing {forecast_horizon_days}-Day Revenue Time-Series Forecast...")
        df = transactions_df.copy()
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        
        # Aggregate daily net revenue
        daily_ts = df.groupby("TransactionDate")["NetRevenue"].sum().sort_index()
        daily_ts = daily_ts.asfreq("D", fill_value=0.0)

        # Use Holt-Winters with additive trend and 7-day weekly seasonality
        try:
            hw_model = ExponentialSmoothing(
                daily_ts,
                trend="add",
                seasonal="add",
                seasonal_periods=7,
                initialization_method="estimated"
            ).fit()
            model_name = "Holt-Winters Exponential Smoothing (Trend+Seasonality)"
            forecast_series = hw_model.forecast(forecast_horizon_days)
            residuals = hw_model.resid
            std_resid = np.std(residuals) if len(residuals) > 0 else (daily_ts.std() * 0.2)
        except Exception as e:
            # Fallback to simple exponential smoothing / moving window
            print(f"[WARN] Holt-Winters fallback triggered ({e}). Using moving trend projection.")
            model_name = "Adaptive Trend Projection"
            rolling_mean = daily_ts.tail(30).mean()
            trend = (daily_ts.tail(14).mean() - daily_ts.tail(60).head(14).mean()) / 30.0
            forecast_values = [max(1000.0, rolling_mean + trend * step) for step in range(1, forecast_horizon_days + 1)]
            last_date = daily_ts.index[-1]
            future_dates = [last_date + pd.Timedelta(days=d) for d in range(1, forecast_horizon_days + 1)]
            forecast_series = pd.Series(forecast_values, index=future_dates)
            std_resid = daily_ts.std() * 0.25

        last_date = daily_ts.index.max()
        future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, forecast_horizon_days + 1)]

        # 95% Confidence Interval (~1.96 * std_resid)
        z_multiplier = 1.96
        forecast_df = pd.DataFrame({
            "ForecastDate": [d.strftime("%Y-%m-%d") for d in future_dates],
            "DayOfWeek": [d.strftime("%A") for d in future_dates],
            "ForecastedRevenue": np.maximum(0.0, forecast_series.values).round(2),
            "LowerBound": np.maximum(0.0, forecast_series.values - z_multiplier * std_resid).round(2),
            "UpperBound": (forecast_series.values + z_multiplier * std_resid).round(2),
            "ModelType": model_name
        })

        # Summary KPIs
        projected_30d_rev = float(forecast_df["ForecastedRevenue"].sum())
        historical_30d_rev = float(daily_ts.tail(30).sum())
        projected_growth_pct = round(((projected_30d_rev - historical_30d_rev) / historical_30d_rev) * 100, 2) if historical_30d_rev > 0 else 0.0

        forecast_summary = {
            "ModelName": model_name,
            "ForecastHorizonDays": forecast_horizon_days,
            "Historical30dRevenue": round(historical_30d_rev, 2),
            "Projected30dRevenue": round(projected_30d_rev, 2),
            "ProjectedGrowthPct": projected_growth_pct,
            "AvgDailyForecastRevenue": round(float(forecast_df["ForecastedRevenue"].mean()), 2),
            "MaxProjectedDay": forecast_df.loc[forecast_df["ForecastedRevenue"].idxmax()]["ForecastDate"],
            "MaxProjectedRevenue": float(forecast_df["ForecastedRevenue"].max())
        }

        print(f"[SUCCESS] Forecasting Complete: Projected 30-day revenue: ${projected_30d_rev:,.2f} ({projected_growth_pct:+.1f}% vs prior 30d).")
        return forecast_df, forecast_summary
