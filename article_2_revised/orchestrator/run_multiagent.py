"""
Orchestrator: fans out to all 4 agents in parallel, collects results.
Each agent runs in its own sandbox — total parallelism, zero shared state.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import User
from agents.generate_dataset import CSV_CONTENT
from agents.statistician_agent import StatisticianAgent
from agents.trend_analyst_agent import TrendAnalystAgent
from agents.anomaly_detector_agent import AnomalyDetectorAgent
from agents.forecaster_agent import ForecasterAgent


def run_agent(agent, csv_content: str) -> dict:
    try:
        response = agent.call(User(content=csv_content))
        return json.loads(response.content)
    except Exception as e:
        print(f"  ✗ {agent.name} FAILED: {e}")
        return {"agent": agent.name, "status": "error", "error": str(e)[:200]}


def run_pipeline():
    agents = [
        StatisticianAgent(),
        TrendAnalystAgent(),
        AnomalyDetectorAgent(),
        ForecasterAgent(),
    ]

    print(f"Starting {len(agents)} agents in parallel...\n")
    overall_start = time.time()

    reports = []
    parallel_start = time.time()

    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {executor.submit(run_agent, agent, CSV_CONTENT): agent.name
                   for agent in agents}
        for future in as_completed(futures):
            result = future.result()
            reports.append(result)
            agent_name = result.get("agent", "unknown")
            elapsed = result.get("elapsed_secs", "?")
            sb_id = result.get("sandbox_id", "?")
            print(f"  ✓ {agent_name} | {elapsed}s | sandbox {sb_id}")

    parallel_elapsed = round(time.time() - parallel_start, 2)

    # Verify all successful agents used distinct sandboxes
    sandbox_ids = [r.get("sandbox_id") for r in reports if r.get("sandbox_id")]
    errors = [r for r in reports if r.get("status") == "error"]
    if errors:
        print(f"\n  ⚠ {len(errors)} agent(s) errored: {[e['agent'] for e in errors]}")
    assert len(set(sandbox_ids)) == len(sandbox_ids), "ERROR: agents shared a sandbox!"
    print(f"\n✅ All {len(sandbox_ids)} successful agents used distinct sandboxes: {sandbox_ids}")

    total_elapsed = round(time.time() - overall_start, 2)
    print(f"Parallel execution: {parallel_elapsed}s | Total: {total_elapsed}s")

    output = {
        "parallel_secs": parallel_elapsed,
        "total_secs": total_elapsed,
        "sandbox_ids": sandbox_ids,
        "reports": reports,
    }
    with open("outputs/multiagent_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("Saved to outputs/multiagent_results.json")
    return output


if __name__ == "__main__":
    run_pipeline()
