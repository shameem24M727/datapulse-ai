import os
import pandas as pd
import numpy as np

sample_dir = r"c:\DataPulse-AI\backend\sample_data"
os.makedirs(sample_dir, exist_ok=True)

# 1. Clean Customers CSV
df_clean = pd.DataFrame({
    "customer_id": [f"CUST-{1000 + i}" for i in range(50)],
    "full_name": [f"Customer {chr(65 + (i % 26))}{i}" for i in range(50)],
    "signup_date": pd.date_range("2026-01-01", periods=50, freq="D").strftime("%Y-%m-%d"),
    "account_tier": ["Enterprise", "Pro", "Free", "Starter", "Enterprise"] * 10,
    "lifetime_spend": np.round(np.random.uniform(500.0, 15000.0, size=50), 2),
    "active": [True] * 40 + [False] * 10,
})
df_clean.to_csv(os.path.join(sample_dir, "clean_customers.csv"), index=False)

# 2. Dirty Transactions CSV (contains missing values, duplicates, and extreme statistical outliers)
np.random.seed(42)
amounts = list(np.random.normal(loc=120.0, scale=25.0, size=95))
amounts.extend([9850.0, 12400.0, 15200.0, -450.0, 0.0])  # Extreme outliers

emails = [f"user{i}@example.com" for i in range(70)] + [None] * 30  # 30% nulls

df_dirty = pd.DataFrame({
    "transaction_id": [f"TX-{10000 + (i if i < 90 else 10001)}" for i in range(100)], # Contains duplicates
    "customer_email": emails,
    "transaction_amount": amounts,
    "currency": ["USD"] * 85 + ["EUR"] * 10 + [None] * 5,
    "payment_method": ["Credit Card", "Wire Transfer", "PayPal", "ACH", "Crypto"] * 20,
    "risk_score": np.random.uniform(1.0, 99.0, size=100),
})
df_dirty.to_csv(os.path.join(sample_dir, "dirty_transactions.csv"), index=False)

# 3. Inventory Products Excel (.xlsx)
df_excel = pd.DataFrame({
    "sku": [f"SKU-{2000 + i}" for i in range(40)],
    "product_name": [f"DataPulse Server Blade Node #{i+1}" for i in range(40)],
    "unit_price": np.round(np.random.uniform(120.0, 2400.0, size=40), 2),
    "stock_quantity": np.random.randint(0, 500, size=40),
    "warehouse_location": ["US-East", "US-West", "EU-Central", "AP-South"] * 10,
    "reorder_needed": [False] * 32 + [True] * 8,
})
df_excel.to_excel(os.path.join(sample_dir, "inventory_products.xlsx"), index=False)

# 4. Empty File
with open(os.path.join(sample_dir, "empty_dataset.csv"), "w") as f:
    pass

# 5. Invalid File format
with open(os.path.join(sample_dir, "invalid_file.txt"), "w") as f:
    f.write("This is a raw text file without structured tabular delimiters.")

print("Sample datasets generated successfully!")
