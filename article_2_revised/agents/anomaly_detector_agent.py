"""
Agent 3: Anomaly Detector
Finds outliers using IQR and Z-score methods inside its own sandbox.
System prompt: Data quality analyst focused on anomalous observations.
"""
from dotenv import load_dotenv
load_dotenv()

import time
import json
from agents.base import User, Assistant, boot_sandbox, write_data_to_sandbox, run_python_in_sandbox, llm_call

SYSTEM_PROMPT = """You are an anomaly detection specialist.
Given outlier data from a revenue dataset, identify the most significant anomalies,
assess their magnitude relative to normal range, and suggest likely causes."""


class AnomalyDetectorAgent:

    name = "anomaly_detector"

    def call(self, user_message: User, files=None) -> Assistant:
        csv_content = user_message.content
        start = time.time()

        sb = boot_sandbox()
        print(f"  [AnomalyDetector] Sandbox {sb.sandbox_id} booted")

        try:
            write_data_to_sandbox(sb, csv_content)

            code = """
import pandas as pd
import numpy as np
import json

df = pd.read_csv('/workspace/data/dataset.csv')
rev = df['revenue']

# IQR method
q1, q3 = rev.quantile(0.25), rev.quantile(0.75)
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
iqr_outliers = df[(rev < lower) | (rev > upper)][['day', 'revenue']].to_dict('records')

# Z-score method
z_scores = np.abs((rev - rev.mean()) / rev.std())
zscore_outliers = df[z_scores > 2.5][['day', 'revenue']].to_dict('records')

result = {
    'iqr_bounds': {'lower': round(float(lower), 2), 'upper': round(float(upper), 2)},
    'iqr_outliers': [{'day': int(r['day']), 'revenue': round(float(r['revenue']), 2)} for r in iqr_outliers],
    'zscore_outliers': [{'day': int(r['day']), 'revenue': round(float(r['revenue']), 2)} for r in zscore_outliers],
    'num_iqr_outliers': len(iqr_outliers),
    'num_zscore_outliers': len(zscore_outliers),
}
print(json.dumps(result))
"""
            raw = run_python_in_sandbox(sb, code)
            anomaly_data = json.loads(raw)

            interpretation = llm_call(
                SYSTEM_PROMPT,
                f"Anomaly detection results:\n{json.dumps(anomaly_data, indent=2)}"
            )

            elapsed = time.time() - start
            return Assistant(content=json.dumps({
                "agent": "anomaly_detector",
                "sandbox_id": sb.sandbox_id,
                "elapsed_secs": round(elapsed, 2),
                "anomaly_data": anomaly_data,
                "interpretation": interpretation
            }))

        finally:
            sb.terminate()
