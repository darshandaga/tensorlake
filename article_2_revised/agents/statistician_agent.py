"""
Agent 1: Statistician
Computes descriptive statistics on the dataset inside its own Tensorlake sandbox.
System prompt: Quantitative analyst focused on distributional properties.
"""
from dotenv import load_dotenv
load_dotenv()

import time
import json
from agents.base import User, Assistant, boot_sandbox, write_data_to_sandbox, run_python_in_sandbox, llm_call

SYSTEM_PROMPT = """You are a quantitative statistician.
Given raw numerical results from a dataset, produce a structured statistical summary.
Include: mean, median, std deviation, skewness, kurtosis, and a brief interpretation.
Be precise and concise. Output only the analysis — no preamble."""


class StatisticianAgent:
    """
    Runs descriptive statistics inside an isolated Tensorlake sandbox.
    Uses numpy and scipy inside the sandbox, then interprets with Claude.
    """

    name = "statistician"

    def call(self, user_message: User, files=None) -> Assistant:
        csv_content = user_message.content
        start = time.time()

        sb = boot_sandbox()
        print(f"  [Statistician] Sandbox {sb.sandbox_id} booted")

        try:
            write_data_to_sandbox(sb, csv_content)

            code = """
import pandas as pd
import numpy as np
from scipy import stats
import json

df = pd.read_csv('/workspace/data/dataset.csv')
rev = df['revenue']

result = {
    'mean': round(float(rev.mean()), 2),
    'median': round(float(rev.median()), 2),
    'std': round(float(rev.std()), 2),
    'min': round(float(rev.min()), 2),
    'max': round(float(rev.max()), 2),
    'skewness': round(float(stats.skew(rev)), 4),
    'kurtosis': round(float(stats.kurtosis(rev)), 4),
    'q25': round(float(rev.quantile(0.25)), 2),
    'q75': round(float(rev.quantile(0.75)), 2),
}
print(json.dumps(result))
"""
            raw = run_python_in_sandbox(sb, code)
            stats_data = json.loads(raw)

            interpretation = llm_call(
                SYSTEM_PROMPT,
                f"Statistical results from the dataset:\n{json.dumps(stats_data, indent=2)}"
            )

            elapsed = time.time() - start
            return Assistant(content=json.dumps({
                "agent": "statistician",
                "sandbox_id": sb.sandbox_id,
                "elapsed_secs": round(elapsed, 2),
                "raw_stats": stats_data,
                "interpretation": interpretation
            }))

        finally:
            sb.terminate()
