"""
Reads all output files and compiles article_metrics.json.
Run this last — after all other pipeline scripts have completed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def out(name):
    return os.path.join(ROOT, "outputs", name)

metrics = {}

# Boot benchmark (Phase 1)
if os.path.exists(out("boot_benchmark.json")):
    with open(out("boot_benchmark.json")) as f:
        b = json.load(f)
    metrics["cold_boot_secs"] = b.get("cold_secs")
    metrics["image_boot_secs"] = b.get("image_secs")
    metrics["boot_speedup"] = b.get("speedup")

# Multi-agent pipeline (Phase 4)
if os.path.exists(out("full_pipeline_results.json")):
    with open(out("full_pipeline_results.json")) as f:
        p = json.load(f)
    metrics["num_analyst_agents"] = p.get("num_analyst_agents")
    metrics["num_total_agents"] = p.get("num_total_agents")
    metrics["parallel_execution_secs"] = p.get("parallel_execution_secs")
    metrics["total_pipeline_secs"] = p.get("total_pipeline_secs")
    metrics["all_sandboxes_unique"] = p.get("all_sandboxes_unique")
    per_agent = [r.get("elapsed_secs") for r in p.get("analyst_reports", []) if r.get("elapsed_secs")]
    if per_agent:
        metrics["avg_agent_time_secs"] = round(sum(per_agent) / len(per_agent), 2)
        metrics["sequential_equivalent_secs"] = round(sum(per_agent), 2)
        metrics["parallelism_speedup"] = round(sum(per_agent) / metrics["parallel_execution_secs"], 2)

# Crash isolation (Phase 3)
if os.path.exists(out("crash_isolation_results.json")):
    with open(out("crash_isolation_results.json")) as f:
        c = json.load(f)
    successful = [r for r in c.get("results", []) if r.get("status") == "success"]
    crashed = [r for r in c.get("results", []) if r.get("status") == "crashed"]
    metrics["crash_isolation"] = "CONFIRMED" if len(successful) == 3 and len(crashed) == 1 else "CHECK_LOGS"
    metrics["crash_test_total_secs"] = c.get("elapsed_secs")

print("=== ARTICLE METRICS ===")
print(json.dumps(metrics, indent=2))
with open(out("article_metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)
print("\nSaved to outputs/article_metrics.json")
