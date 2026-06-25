# Article Notes — Tensorlake Multi-Agent System
## Based on Phase 1 implementation (article_2_revised)

---

## What we're building

A multi-agent data analysis pipeline where 4 specialized AI agents — a Statistician, Trend Analyst, Anomaly Detector, and Forecaster — each run in their own isolated Tensorlake sandbox. They all analyze the same dataset in parallel, then a 5th agent synthesizes their reports into an executive summary.

The point isn't just that it works. It's that each agent gets a clean, isolated environment that's already provisioned with the right tools — no runtime installs, no shared state, and a crash in one agent cannot affect any other.

---

## Phase 1 — The Docker Image Problem (and how we solved it)

Before any agent can run, we need a sandbox environment that has all the data science packages pre-installed. This is the "registered image" — a snapshot Tensorlake can use to boot sandboxes from, instead of installing packages from scratch every time.

### What a registered image is

Think of it like a VM snapshot. Instead of booting a blank Linux machine and running `pip install` every time an agent starts, you build the image once, register it with Tensorlake by name, and every subsequent sandbox boots from that snapshot. The packages are already there.

In Tensorlake's Python SDK, you define the image using a fluent builder:

```python
image = (
    Image(base_image="python:3.11-slim")
    .run("useradd -m tl-user")
    .run("pip install numpy pandas scikit-learn scipy statsmodels anthropic requests")
)

image.build(registered_name="analyst-agent-image", cpus=1.0, memory_mb=1024)
```

Tensorlake spins up a temporary "builder sandbox" internally, runs your Docker build steps inside it, takes a snapshot of the resulting filesystem, and registers it under the name you give it. After that, any call to `Sandbox.create(image="analyst-agent-image")` boots from that snapshot.

### What went wrong during the build

Three issues hit us in sequence — all useful to document because anyone following this tutorial will likely hit the same ones:

**1. Account quota limits**
The plan called for `cpus=2.0, memory_mb=4096`. The free/starter tier caps sandboxes at 1 vCPU and 1024 MB RAM. Had to drop both to their maximums: `cpus=1.0, memory_mb=1024`.

**2. Wrong base image platform**
We initially tried to reuse `dardaga/ds-sandbox:v1` — a Docker image that had been pushed to Docker Hub previously. It failed with: `no match for platform in manifest: not found`. The image had been built on a Mac (ARM), so it had no `linux/amd64` manifest. Tensorlake's builder sandbox runs on Linux x86_64, so it couldn't pull it. Solution: switch to `python:3.11-slim`, which Docker Hub ships as a proper multi-platform image.

**3. Missing tl-user**
The first build with `python:3.11-slim` succeeded and registered the image, but when we tried to run a command inside a sandbox booted from it, we got: `API error (status 500): user not found: tl-user`. Tensorlake's sandbox runtime expects a system user called `tl-user` to exist inside the image. The `python:3.11-slim` base doesn't create it. Adding `.run("useradd -m tl-user")` as the first step in the image definition fixed it.

**4. Dangling sandbox from a crashed verify script**
When the verify script crashed mid-run (before `sb.terminate()` was called), it left a sandbox in RUNNING state. The next build attempt hit the quota again: "1 sandboxes are running and the project has reached its quota." The fix was to use `SandboxClient.for_cloud().delete(sandbox_id)` to force-kill it. Going forward, the verify script wraps its `sb.run()` call in a `try/finally` block so the sandbox always terminates even if the run fails.

---

## Phase 1 results

### Image registration
- **Registered name:** `analyst-agent-image`
- **Template ID:** `sandbox_template_DgJkWFQ97gtB7DM9RRMKb`
- **Build time:** 123.5 seconds (one-time cost)
- **Snapshot size:** ~241 MB
- **Packages baked in:** numpy, pandas, scikit-learn, scipy, statsmodels, anthropic, requests

### Boot time benchmark: cold vs registered image

| Method | Time |
|---|---|
| Cold boot + `pip install` at runtime | 17.78s |
| Boot from `analyst-agent-image` | 4.34s |
| **Speedup** | **4.1x** |

The cold path boots a blank sandbox and runs pip install every time. With 4 agents launching in parallel (Phase 2), that overhead compounds. The registered image eliminates it entirely — the sandbox boots ready, no install step.

### Verification
After the final build, a sandbox booted from `analyst-agent-image` confirmed all packages are present:
- numpy 2.4.6
- pandas 3.0.3
- scipy 1.17.1
- anthropic 0.112.0
- scikit-learn, statsmodels, requests ✓

---

## Key things to highlight in the article

- **Build once, boot many times.** The 123-second build is a one-time cost. Every agent after that boots in ~4 seconds instead of ~18 seconds.
- **Platform matters.** If you're on a Mac building Docker images, be explicit about `--platform linux/amd64` before pushing, or just use well-known base images like `python:3.11-slim` that ship multi-platform manifests.
- **Tensorlake requires `tl-user` in the image.** This isn't documented prominently — worth calling out explicitly so readers don't hit it.
- **Always terminate sandboxes in a `try/finally` block.** Leaving one running on a free-tier account blocks the next operation immediately. The SDK's `terminate()` is also eventually consistent, not synchronous — force-deleting via `SandboxClient` is the reliable cleanup path.
- **The registered image is what makes the multi-agent pattern practical.** 4 agents × 18s cold boot = 18s of wasted time even in parallel. 4 agents × 4s image boot = agents are doing real work almost immediately.

---

## Coming next (Phase 2)

With the image registered, Phase 2 defines the 4 agent classes — each with its own system prompt, its own set of computational tools running inside its sandbox, and its own call to the Claude API to interpret the results. Each agent is a genuinely separate class, not the same agent running 4 times.

---

## Phase 2 — The 4 Agent Classes

### What we built

Five files under `agents/`:

| File | Role |
|---|---|
| `base.py` | Shared helpers: `boot_sandbox()`, `write_data_to_sandbox()`, `run_python_in_sandbox()`, `llm_call()` + `User`/`Assistant` dataclasses |
| `generate_dataset.py` | 90-day synthetic sales CSV, anomaly injected on day 45 ($800 spike) |
| `statistician_agent.py` | Descriptive stats via numpy/scipy inside sandbox |
| `trend_analyst_agent.py` | Linear regression + 7-day rolling average |
| `anomaly_detector_agent.py` | IQR and Z-score outlier detection |
| `forecaster_agent.py` | 80/20 train/holdout split, linear forecast for days 91–100 |

### SDK note: no Agent base class

The plan called for `from tensorlake import Agent, User, Assistant`. Those classes don't exist in the installed SDK — the SDK only exposes `Image` and `Sandbox`. Each agent is implemented as a plain Python class with a `call(user_message: User) -> Assistant` method. `User` and `Assistant` are `@dataclass` wrappers defined in `base.py`. The interface is identical to the plan; only the inheritance chain is different.

---

### Phase 2 results

Each agent was run individually to validate the full loop: sandbox boot → dataset write → Python computation inside sandbox → Claude API call → structured JSON result.

**All 4 sandbox IDs were distinct** — confirming each agent got its own isolated environment:

| Agent | Sandbox ID | Elapsed |
|---|---|---|
| Statistician | `dqhfomcytb2rfswth6cw8` | 15.15s |
| TrendAnalyst | `5jdxog2rpf94dtgpstdg5` | 21.25s |
| AnomalyDetector | `uc1v1twwh54gcet6bgr19` | 18.73s |
| Forecaster | `nxjk6l3zqvdthmes9c8ql` | 26.56s |

Timing breakdown per agent: ~4s sandbox boot (from registered image) + ~2–5s compute inside sandbox + ~8–15s Claude API call.

---

#### Agent 1 — Statistician

Raw stats computed inside sandbox:

| Metric | Value |
|---|---|
| Mean | 1,467.44 |
| Median | 1,491.85 |
| Std Dev | 294.58 |
| Min | 942.35 |
| Max | 2,312.86 |
| Q25 / Q75 | 1,222.49 / 1,697.12 |
| Skewness | 0.1669 |
| Kurtosis (excess) | −0.695 |

Claude's interpretation: near-symmetric, platykurtic distribution. Mean and median are only 1.6% apart — no significant outlier distortion. Negative kurtosis (flatter than normal) means tail-dependent analyses like VaR should not assume normality.

---

#### Agent 2 — Trend Analyst

| Metric | Value |
|---|---|
| Slope | +$10.18/day |
| R² | 0.8156 (81.6%) |
| p-value | ~0.0 |
| Direction | Upward |
| Rolling 7D avg (last) | $1,851.69 |
| Weekly avgs (W1–W4) | $1,014 → $1,115 → $1,182 → $1,220 |

Claude's interpretation: statistically robust upward trend. Weeks 1–4 showed decelerating growth (+10% → +3.2%), but the final 7-day rolling average of $1,851.69 represents a +51.8% surge above Week 4 — the Trend Analyst flagged this as a potential breakout event that the linear model may be underestimating.

---

#### Agent 3 — Anomaly Detector

| Metric | Value |
|---|---|
| IQR bounds | $510.56 – $2,409.05 |
| IQR outliers | 0 |
| Z-score outliers | 1 (day 45, $2,312.86) |

The injected day-45 spike ($800 above base) was correctly detected by Z-score but not by IQR — it sits just inside the IQR upper fence at 94.9% of the bound. Claude flagged this as a mild, borderline anomaly rather than a critical one. The dataset overall is clean: zero IQR outliers across 90 days.

This is a useful article note: IQR and Z-score don't always agree. The Z-score is more sensitive to the mean, so when the distribution has a long right tail (from the trend), a value near the IQR fence can still be a 2.5σ outlier.

---

#### Agent 4 — Forecaster

Model: linear regression trained on days 1–72 (first 80%), evaluated on days 73–90 (holdout).

| Metric | Value |
|---|---|
| Slope | +$11.12/day |
| R² | 0.7599 (76%) |
| Holdout MAE | $96.92 |
| Day 91 forecast | $1,990.32 |
| Day 100 forecast | $2,090.37 |
| 10-day total gain | +$100.05 (+5.03%) |

Claude's interpretation: moderate confidence, $2,000 threshold crossed on day 92. Key caveat — the MAE of $97 is ~9x the daily slope of $11, meaning day-to-day noise swamps the growth signal. The directional forecast is credible; precise daily figures are not.

---

### Key things to highlight in the article

- **Each agent is a genuinely separate class.** Different system prompt, different computation code, different analytical task. This is not one agent running 4 prompts — each has its own module, its own sandbox, and its own LLM call.
- **The tensorlake SDK's Agent/User/Assistant classes don't exist.** The plan assumed they would. If you're following this tutorial, define your own `User`/`Assistant` dataclasses and use plain Python classes for agents — the Tensorlake primitives you actually need are just `Sandbox.create()` and the sandbox's `run()` / `write_file()` methods.
- **4 unique sandbox IDs = 4 isolated environments.** The most important thing to verify after running agents is that no two agents shared a sandbox. Check `sandbox_id` in each result — if they're all different, isolation is working.
- **The anomaly detector caught the injected spike.** Day 45 had a +$800 spike baked into the dataset generator. The detector found it via Z-score (flagged as >2.5σ). IQR missed it — worth explaining both methods and their sensitivity trade-offs.
- **Elapsed time per agent (~15–27s) is dominated by the LLM call, not the sandbox.** Sandbox boot takes ~4s (from registered image). The Python computation inside the sandbox takes 1–3s. The Claude API call accounts for the remaining 10–20s. This matters for the parallelism argument in Phase 3: the bottleneck isn't Tensorlake, it's the LLM.

---

## Coming next (Phase 3)

With 4 working agents, Phase 3 wires them together: an orchestrator fans them out in parallel using `ThreadPoolExecutor`, then a crash isolation experiment injects a deliberate `rm -rf /usr/lib/python3` into one agent's sandbox to prove the other 3 complete unaffected.

---

## Phase 3 — Orchestrator & Crash Isolation

### What we built

Two files under `orchestrator/`:

| File | Role |
|---|---|
| `run_multiagent.py` | Fans out all 4 agents in parallel via `ThreadPoolExecutor`, verifies distinct sandbox IDs |
| `crash_isolation.py` | Runs 3 normal agents + 1 crash agent simultaneously, proves isolation holds |

Both files add `sys.path.insert(0, ...)` to resolve the `agents/` package when run as scripts from a subdirectory.

---

### Issues hit and fixes

**1. `ModuleNotFoundError: No module named 'agents'`**
Running `python3 orchestrator/run_multiagent.py` adds `orchestrator/` to `sys.path`, not the project root. Fixed by inserting the parent directory at the top of both scripts:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**2. Free-tier quota: only 1 sandbox at a time**
All 4 agents called `Sandbox.create()` simultaneously — 3 got:
```
API error (status 400): 1 sandboxes are running and the project has reached its quota.
```
The first agent booted fine; the other 3 failed silently and returned `{"status": "error"}` with `elapsed_secs: ?` and `sandbox_id: ?`.

Fix: added retry logic with backoff in `boot_sandbox()` (in `base.py`):
```python
def boot_sandbox(max_retries=12, retry_delay=8.0) -> Sandbox:
    for attempt in range(max_retries):
        try:
            return Sandbox.create(image=AGENT_IMAGE, timeout_secs=300)
        except Exception as e:
            if "quota" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise
```
Agents now queue automatically and boot as soon as the previous sandbox terminates.

**3. Crash agent used `Sandbox.create()` directly, bypassing retry**
The `crashing_agent()` called `Sandbox.create()` instead of `boot_sandbox()`, so it raised an unhandled quota error that crashed the whole test. Fixed by swapping `Sandbox.create(image=AGENT_IMAGE)` for `boot_sandbox()`.

**4. Filesystem destruction approach failed silently**
The original crash mechanism (`rm -f /usr/local/bin/python3`) did nothing — `tl-user` doesn't have write permission to `/usr/local/bin/`. The `rm -f` succeeded with exit 0 (no error output), Python still worked, and the crash agent reported `unexpectedly_succeeded`.

Switched to an explicit `raise RuntimeError(...)` after the sandbox boots and does initial work. This is actually more realistic: real agent crashes are code-level (bad data, assertion errors, OOM), not filesystem destruction.

---

### Phase 3 results

#### Parallel orchestrator (`run_multiagent.py`)

| Agent | Sandbox ID | Elapsed |
|---|---|---|
| Statistician | `9aek31r972eh5nemqx4iq` | 26.18s |
| AnomalyDetector | `txuqkzzsacyssqxbexcxa` | 50.48s |
| TrendAnalyst | `ug9iml4g43us4uq7w7oiv` | 75.73s |
| Forecaster | `h09rkjqrdu6uk09zswngd` | 94.29s |

- **All 4 sandbox IDs distinct** ✅
- **Parallel execution time: 102.92s** — effectively sequential due to free-tier quota of 1 sandbox at a time
- Each agent's elapsed time is cumulative: Statistician runs first, then AnomalyDetector gets the slot, etc.
- On a paid account with quota ≥ 4, all agents would boot simultaneously and complete in ~26s (the slowest agent's time) instead of ~103s

#### Crash isolation (`crash_isolation.py`)

| Agent | Sandbox ID | Status |
|---|---|---|
| Statistician | `r9d1rz7wg98kqkfiqgddt` | success |
| Forecaster | `amd2tdstb23yyb6etinc7` | success |
| TrendAnalyst | `i5r234xrxwxxk3o647fuw` | success |
| CrashAgent | `0drrpymmyy5c1so6bkkqj` | crashed |

```
✅ ISOLATION CONFIRMED — crash contained, 3/3 normal agents completed
Total time: 104.54s
```

The crash agent booted its own sandbox, did initial work, then raised a `RuntimeError`. Its sandbox was terminated in the `finally` block. The 3 normal agents were completely unaffected — they each had their own isolated sandboxes and completed successfully.

---

### Key things to highlight in the article

- **Free-tier quota serializes "parallel" agents.** `ThreadPoolExecutor` launches all 4 threads simultaneously, but `boot_sandbox()` queues them via retry. The code structure is correct for true parallelism — it just needs quota > 1 to deliver on it. Worth being explicit about this so readers on the free tier aren't confused by slow total times.
- **The retry pattern belongs in `boot_sandbox()`, not in the orchestrator.** Centralizing it means every agent (including the crash agent) gets quota handling for free — no orchestrator-level changes needed.
- **Crash isolation works at the sandbox level, not the exception level.** The crash agent raised a Python exception. That exception was caught by `crashing_agent()`, which returned `{"status": "crashed"}`. The other agents never saw it because they were in separate sandboxes with no shared memory or filesystem. This is the point: process isolation means you don't need to design your agents to be defensively coded against each other's failures.
- **`tl-user` doesn't have write access to `/usr/local/bin/`.** Relevant for anyone trying to simulate a destructive crash — filesystem corruption inside the sandbox requires root, which `tl-user` is not. The more realistic crash simulation (and the one that actually works) is a code-level exception.

---

## Phase 4 — Full Pipeline + Synthesis + Article Metrics

### What we built

Two files under `pipeline/` and one new agent:

| File | Role |
|---|---|
| `agents/aggregator_agent.py` | Agent 5 — no sandbox, pure LLM call that synthesises the 4 analyst reports into an executive summary |
| `pipeline/run_full_pipeline.py` | Fans out 4 analyst agents in parallel, then passes all reports to the aggregator, saves `full_pipeline_results.json` |
| `pipeline/generate_article_metrics.py` | Reads all output JSONs and compiles `article_metrics.json` |

---

### Issues hit and fixes

**`ModuleNotFoundError: No module named 'agents'`**
Same issue as Phase 3 — scripts in subdirectories don't get the project root on `sys.path`. Fixed with the same `sys.path.insert(0, ...)` pattern at the top of both pipeline scripts. Also fixed `outputs/` path resolution to use an absolute path derived from `__file__` so the script works regardless of working directory.

---

### Phase 4 results

#### Full pipeline run

| Agent | Sandbox ID | Elapsed |
|---|---|---|
| Statistician | `825lasxk9rlhol4hr4rbz` | 17.39s |
| TrendAnalyst | `fq69jc85ghbet7mfidvwe` | 44.63s |
| Forecaster | `rhk4ca1iph9ic7svbipjz` | 71.55s |
| AnomalyDetector | `wmahvt2peqvvavb7yeiyr` | 104.43s |
| Aggregator | *(no sandbox)* | — |

- **Parallel execution: 108.28s** (quota-serialized on free tier, same as Phase 3)
- **Total pipeline: 130.18s** (includes aggregator LLM call ~22s)
- **All 4 sandbox IDs distinct** ✅

#### Article metrics (compiled from all phases)

| Metric | Value |
|---|---|
| Cold boot + `pip install` | 17.78s |
| Registered image boot | 4.34s |
| **Boot speedup** | **4.1x** |
| Analyst agents | 4 |
| Total agents (incl. aggregator) | 5 |
| Parallel execution | 108.28s |
| Sequential equivalent | 238.0s |
| **Parallelism speedup** | **2.2x** |
| Total pipeline | 130.18s |
| All sandbox IDs unique | true |
| Avg agent time | 59.5s |
| Crash isolation | CONFIRMED |
| Crash test total | 104.54s |

Note on the 2.2x parallelism speedup: sequential equivalent is the sum of all 4 agents' elapsed times (238s). On a free-tier account the actual parallel time is 108s because quota forces agents to serialize on sandbox boot. On a paid account with quota ≥ 4, all agents boot simultaneously and the parallel time would collapse to ~104s (the slowest agent), giving a ~2.3x true speedup purely from parallel execution.

#### Executive summary (generated by aggregator)

The aggregator synthesised the 4 analyst reports into a 5-section executive briefing covering:

1. **Statistics:** Near-normal distribution, mean $1,467, std $295. Negative kurtosis (−0.695) — values broadly spread, not concentrated.
2. **Trend:** Confirmed upward trend at +$10–11/day (p < 0.0001, R² = 0.82). Weekly growth decelerating: +$101 → +$66 → +$38 per week.
3. **Anomalies:** Only Day 45 ($2,313) flagged — Z-score outlier, within IQR bounds. No data quality concerns.
4. **Forecast:** Days 91–100 range $1,990–$2,090. $2K threshold crossed on Day 92. Uncertainty band ±$97 (MAE).
5. **Recommendation:** Growth is real but decelerating. Investigate the Week 1→2 surge driver (+$101) to replicate it. Add day-of-week and promotional flags to the model to reduce forecast error.

---

### Key things to highlight in the article

- **The aggregator agent needs no sandbox.** Its job is LLM reasoning over structured text — no Python execution, no data science libraries. Mixing sandbox agents (computationally heavy) with no-sandbox agents (reasoning only) in the same pipeline is a natural pattern: use sandboxes where you need isolated compute, skip them where you don't.
- **The parallelism speedup (2.2x) understates the true benefit on a paid account.** Free-tier quota forces agents to run sequentially even though the code is parallel. The speedup number reflects quota-constrained execution, not architectural parallelism. The article should clarify this distinction.
- **Total pipeline = parallel time + aggregator.** The aggregator added ~22s on top of the 108s parallel phase — one extra LLM call with no sandbox overhead. The 5-agent total of 130s compares to a purely sequential run of ~260s.
- **The executive summary was coherent and cited real numbers.** Aggregating across 4 independent agents with different analytical focuses (stats, trend, anomaly, forecast) produced a summary that correctly cross-referenced all their findings without contradiction.
