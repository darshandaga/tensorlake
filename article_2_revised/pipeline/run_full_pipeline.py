"""
Full pipeline:
  Phase 1: 4 analyst agents run in parallel, each in its own sandbox (analyst-agent-image)
  Phase 2: Aggregator agent synthesises all 4 reports — no sandbox, pure LLM
  Captures all article metrics.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.base import User

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from agents.generate_dataset import CSV_CONTENT
from agents.statistician_agent import StatisticianAgent
from agents.trend_analyst_agent import TrendAnalystAgent
from agents.anomaly_detector_agent import AnomalyDetectorAgent
from agents.forecaster_agent import ForecasterAgent
from agents.aggregator_agent import AggregatorAgent


def run_agent(agent, csv_content: str) -> dict:
    try:
        response = agent.call(User(content=csv_content))
        result = json.loads(response.content)
        result["status"] = "success"
        return result
    except Exception as e:
        return {"agent": getattr(agent, 'name', '?'), "status": "error", "error": str(e)[:200]}


def run_full_pipeline():
    print("=" * 60)
    print("TENSORLAKE MULTI-AGENT PIPELINE")
    print("=" * 60)

    analyst_agents = [
        StatisticianAgent(),
        TrendAnalystAgent(),
        AnomalyDetectorAgent(),
        ForecasterAgent(),
    ]

    # --- PHASE 1: Parallel analyst agents ---
    print(f"\n[Phase 1] Running {len(analyst_agents)} analyst agents in parallel...")
    overall_start = time.time()
    parallel_start = time.time()

    reports = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_agent, agent, CSV_CONTENT): agent.name
            for agent in analyst_agents
        }
        for future in as_completed(futures):
            result = future.result()
            reports.append(result)
            print(f"  ✓ {result.get('agent')} | {result.get('elapsed_secs')}s "
                  f"| sandbox {result.get('sandbox_id', 'N/A')}")

    parallel_elapsed = round(time.time() - parallel_start, 2)
    print(f"\n  Parallel execution: {parallel_elapsed}s")

    # --- PHASE 2: Aggregation ---
    print("\n[Phase 2] Aggregator synthesising reports...")
    aggregator = AggregatorAgent()
    agg_response = aggregator.call(User(content=json.dumps(reports)))
    synthesis = agg_response.content

    total_elapsed = round(time.time() - overall_start, 2)

    print("\n" + "=" * 60)
    print("EXECUTIVE SUMMARY")
    print("=" * 60)
    print(synthesis)

    # --- Collect article metrics ---
    sandbox_ids = [r.get("sandbox_id") for r in reports if r.get("sandbox_id")]
    output = {
        "num_analyst_agents": len(analyst_agents),
        "num_total_agents": len(analyst_agents) + 1,  # +1 for aggregator
        "parallel_execution_secs": parallel_elapsed,
        "total_pipeline_secs": total_elapsed,
        "sandbox_ids": sandbox_ids,
        "all_sandboxes_unique": len(set(sandbox_ids)) == len(sandbox_ids),
        "analyst_reports": reports,
        "executive_summary": synthesis,
    }

    out_path = os.path.join(ROOT, "outputs", "full_pipeline_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nTotal time: {total_elapsed}s")
    print("Saved to outputs/full_pipeline_results.json")
    return output


if __name__ == "__main__":
    run_full_pipeline()
