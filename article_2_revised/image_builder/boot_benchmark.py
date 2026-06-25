"""
Baseline benchmark for the article.
Measures how much faster analyst-agent-image boots vs cold + runtime install.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import time
from tensorlake.sandbox import Sandbox

results = {}

# --- Cold boot + runtime pip install ---
print("=== Cold boot + runtime pip install ===")
start = time.time()
sb = Sandbox.create()
sb.run("python3", ["-m", "pip", "install", "--break-system-packages",
                    "numpy", "pandas", "scikit-learn", "scipy", "anthropic"])
sb.run("python3", ["-c", "import numpy, pandas, sklearn; print('cold: ready')"])
results["cold_secs"] = round(time.time() - start, 2)
sb.terminate()
print(f"Cold: {results['cold_secs']}s")

# --- Registered image boot ---
print("\n=== Registered image boot (analyst-agent-image) ===")
start = time.time()
sb = Sandbox.create(image="analyst-agent-image")
sb.run("python3", ["-c", "import numpy, pandas, sklearn; print('image: ready')"])
results["image_secs"] = round(time.time() - start, 2)
sb.terminate()
print(f"Image: {results['image_secs']}s")

speedup = results["cold_secs"] / results["image_secs"]
results["speedup"] = round(speedup, 2)
print(f"\nSpeedup: {speedup:.1f}x faster with registered image")

with open("outputs/boot_benchmark.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved to outputs/boot_benchmark.json")
