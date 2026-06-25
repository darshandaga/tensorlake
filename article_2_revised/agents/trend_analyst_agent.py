"""
Agent 2: Trend Analyst
Detects linear and rolling trends in the revenue time series.
System prompt: Time series analyst focused on directional movement.
"""
from dotenv import load_dotenv
load_dotenv()

import time
import json
from agents.base import User, Assistant, boot_sandbox, write_data_to_sandbox, run_python_in_sandbox, llm_call

SYSTEM_PROMPT = """You are a time series trend analyst.
Given trend metrics from a revenue dataset, identify the directional movement,
growth rate, and key inflection points. Be specific about slope and confidence."""


class TrendAnalystAgent:

    name = "trend_analyst"

    def call(self, user_message: User, files=None) -> Assistant:
        csv_content = user_message.content
        start = time.time()

        sb = boot_sandbox()
        print(f"  [TrendAnalyst] Sandbox {sb.sandbox_id} booted")

        try:
            write_data_to_sandbox(sb, csv_content)

            code = """
import pandas as pd
import numpy as np
from scipy import stats
import json

df = pd.read_csv('/workspace/data/dataset.csv').sort_values('day')
rev = df['revenue'].values
days = df['day'].values

# Linear regression over full series
slope, intercept, r_value, p_value, std_err = stats.linregress(days, rev)

# Rolling 7-day average
rolling_avg = pd.Series(rev).rolling(7).mean().dropna().tolist()

# Week-over-week comparison (first 4 weeks)
weekly = [float(np.mean(rev[i*7:(i+1)*7])) for i in range(4) if (i+1)*7 <= len(rev)]

result = {
    'slope_per_day': round(float(slope), 4),
    'r_squared': round(float(r_value**2), 4),
    'p_value': round(float(p_value), 6),
    'trend_direction': 'upward' if slope > 0 else 'downward',
    'rolling_7d_avg_last': round(rolling_avg[-1], 2) if rolling_avg else None,
    'weekly_averages': [round(w, 2) for w in weekly],
}
print(json.dumps(result))
"""
            raw = run_python_in_sandbox(sb, code)
            trend_data = json.loads(raw)

            interpretation = llm_call(
                SYSTEM_PROMPT,
                f"Trend metrics from dataset:\n{json.dumps(trend_data, indent=2)}"
            )

            elapsed = time.time() - start
            return Assistant(content=json.dumps({
                "agent": "trend_analyst",
                "sandbox_id": sb.sandbox_id,
                "elapsed_secs": round(elapsed, 2),
                "trend_data": trend_data,
                "interpretation": interpretation
            }))

        finally:
            sb.terminate()
