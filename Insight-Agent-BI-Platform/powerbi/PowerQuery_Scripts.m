// ==============================================================================
// InsightAgent Power BI Desktop - Power Query (M) Automated Import Scripts
// Open Power BI Desktop -> Home -> Advanced Editor (or Blank Query) -> Paste M-Code
// Note: Update "FolderPath" parameter to point to your data/powerbi_exports/ folder
// ==============================================================================

// ------------------------------------------------------------------------------
// 0. Base Parameter: FolderPath
// ------------------------------------------------------------------------------
// Create a Parameter named 'FolderPath' in Power Query:
// Type: Text
// Current Value: "C:\Users\Admin\Documents\code\E-G-InsightAgent\data\powerbi_exports\"

// ------------------------------------------------------------------------------
// 1. Query: dim_date
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "dim_date.csv"), [Delimiter=",", Columns=13, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"DateKey", Int64.Type}, 
        {"FullDate", type date}, 
        {"Year", Int64.Type}, 
        {"Quarter", Int64.Type}, 
        {"QuarterName", type text}, 
        {"Month", Int64.Type}, 
        {"MonthName", type text}, 
        {"MonthShort", type text}, 
        {"Day", Int64.Type}, 
        {"DayOfWeek", Int64.Type}, 
        {"DayName", type text}, 
        {"IsWeekend", Int64.Type}, 
        {"WeekOfYear", Int64.Type}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 2. Query: dim_customer
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "dim_customer.csv"), [Delimiter=",", Columns=17, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"CustomerID", type text}, 
        {"CustomerName", type text}, 
        {"CustomerSegment", type text}, 
        {"Region", type text}, 
        {"State", type text}, 
        {"LastPurchaseDate", type date}, 
        {"Frequency", Int64.Type}, 
        {"Monetary", type number}, 
        {"AvgOrderValue", type number}, 
        {"AvgProfitMargin", type number}, 
        {"ReturnCount", Int64.Type}, 
        {"Recency", Int64.Type}, 
        {"ReturnRate", type number}, 
        {"Cluster", Int64.Type}, 
        {"RFM_Segment", type text}, 
        {"RFM_Score", Int64.Type}, 
        {"ChurnRisk", type text}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 3. Query: dim_product
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "dim_product.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"ProductID", type text}, 
        {"ProductName", type text}, 
        {"Category", type text}, 
        {"BasePrice", type number}, 
        {"CostPrice", type number}, 
        {"StandardMarginPercent", type number}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 4. Query: dim_channel
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "dim_channel.csv"), [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"ChannelID", type text}, 
        {"ChannelName", type text}, 
        {"ChannelType", type text}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 5. Query: fact_transactions
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "fact_transactions.csv"), [Delimiter=",", Columns=21, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"TransactionID", type text}, 
        {"DateKey", Int64.Type}, 
        {"TransactionDate", type date}, 
        {"CustomerID", type text}, 
        {"ProductID", type text}, 
        {"ChannelID", type text}, 
        {"Quantity", Int64.Type}, 
        {"UnitPrice", type number}, 
        {"CostPrice", type number}, 
        {"DiscountRate", type number}, 
        {"GrossRevenue", type number}, 
        {"DiscountAmount", type number}, 
        {"NetRevenue", type number}, 
        {"TotalCost", type number}, 
        {"Profit", type number}, 
        {"ProfitMargin", type number}, 
        {"PaymentMethod", type text}, 
        {"IsReturned", Int64.Type}, 
        {"Anomaly_Flag", Int64.Type}, 
        {"Anomaly_Score", type number}, 
        {"Detected_Anomaly_Type", type text}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 6. Query: fact_anomalies
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "fact_anomalies.csv"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"TransactionID", type text}, 
        {"DateKey", Int64.Type}, 
        {"TransactionDate", type date}, 
        {"CustomerID", type text}, 
        {"ProductID", type text}, 
        {"ChannelID", type text}, 
        {"Quantity", Int64.Type}, 
        {"NetRevenue", type number}, 
        {"DiscountRate", type number}, 
        {"Profit", type number}, 
        {"ProfitMargin", type number}, 
        {"Anomaly_Score", type number}, 
        {"Detected_Anomaly_Type", type text}, 
        {"Investigation_Status", type text}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 7. Query: fact_forecasts
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "fact_forecasts.csv"), [Delimiter=",", Columns=7, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"DateKey", Int64.Type}, 
        {"ForecastDate", type date}, 
        {"DayOfWeek", type text}, 
        {"ForecastedRevenue", type number}, 
        {"LowerBound", type number}, 
        {"UpperBound", type number}, 
        {"ModelType", type text}
    })
in
    #"Changed Type"


// ------------------------------------------------------------------------------
// 8. Query: fact_rfm_segments
// ------------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(FolderPath & "fact_rfm_segments.csv"), [Delimiter=",", Columns=8, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"RFM_Segment", type text}, 
        {"CustomerCount", Int64.Type}, 
        {"TotalRevenue", type number}, 
        {"AvgRevenuePerCustomer", type number}, 
        {"AvgFrequency", type number}, 
        {"AvgRecencyDays", type number}, 
        {"AvgMarginPercent", type number}, 
        {"RevenueSharePct", type number}
    })
in
    #"Changed Type"
