"""
Generates a synthetic sales dataset (CSV) used by all 4 agents.
Run once before Phase 3.
"""
import csv
import random
import io
import math

random.seed(42)
rows = []
for day in range(1, 91):  # 90 days of data
    base = 1000 + 10 * day
    # inject an anomaly on day 45
    spike = 800 if day == 45 else 0
    revenue = round(base + random.gauss(0, 80) + spike, 2)
    units = int(revenue / (15 + random.gauss(0, 1.5)))
    rows.append({"day": day, "revenue": revenue, "units": units,
                 "region": random.choice(["North", "South", "East", "West"])})

buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=["day", "revenue", "units", "region"])
writer.writeheader()
writer.writerows(rows)

CSV_CONTENT = buf.getvalue()

if __name__ == "__main__":
    import os
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/dataset.csv", "w") as f:
        f.write(CSV_CONTENT)
    print(f"Dataset written: {len(rows)} rows")
    print("Saved to outputs/dataset.csv")
