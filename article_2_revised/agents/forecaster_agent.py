"""
Agent 4: Forecaster
Fits a linear model on the first 80% of data and predicts the next 10 days.
System prompt: Revenue forecasting analyst.
"""
from dotenv import load_dotenv
load_dotenv()

import time
import json
from agents.base import User, Assistant, boot_sandbox, write_data_to_sandbox, run_python_in_sandbox, llm_call

SYSTEM_PROMPT = """You are a revenue forecasting analyst.
Given a linear forecast for the next 10 days of revenue, interpret the predictions:
identify expected growth, confidence level, and business implications."""


class ForecasterAgent:

    name = "forecaster"

    def call(self, user_message: User, files=None) -> Assistant:
        csv_content = user_message.content
        start = time.time()

        sb = boot_sandbox()
        print(f"  [Forecaster] Sandbox {sb.sandbox_id} booted")

        try:
            write_data_to_sandbox(sb, csv_content)

            code = """
import pandas as pd
import numpy as np
from scipy import stats
import json

df = pd.read_csv('/workspace/data/dataset.csv').sort_values('day')
split = int(len(df) * 0.8)
train = df.iloc[:split]

# Fit on train set
slope, intercept, r_val, _, _ = stats.linregress(train['day'], train['revenue'])

# Predict next 10 days beyond the dataset
last_day = int(df['day'].max())
future_days = list(range(last_day + 1, last_day + 11))
predictions = [round(intercept + slope * d, 2) for d in future_days]

# Evaluate on holdout (last 20%)
test = df.iloc[split:]
test_preds = [intercept + slope * d for d in test['day']]
mae = float(np.mean(np.abs(test['revenue'].values - test_preds)))

result = {
    'model': 'linear_regression',
    'slope_per_day': round(float(slope), 4),
    'r_squared': round(float(r_val**2), 4),
    'holdout_mae': round(mae, 2),
    'forecast': [{'day': d, 'predicted_revenue': p} for d, p in zip(future_days, predictions)],
}
print(json.dumps(result))
"""
            raw = run_python_in_sandbox(sb, code)
            forecast_data = json.loads(raw)

            interpretation = llm_call(
                SYSTEM_PROMPT,
                f"Forecast results:\n{json.dumps(forecast_data, indent=2)}"
            )

            elapsed = time.time() - start
            return Assistant(content=json.dumps({
                "agent": "forecaster",
                "sandbox_id": sb.sandbox_id,
                "elapsed_secs": round(elapsed, 2),
                "forecast_data": forecast_data,
                "interpretation": interpretation
            }))

        finally:
            sb.terminate()
