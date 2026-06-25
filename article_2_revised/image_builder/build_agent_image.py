from dotenv import load_dotenv
load_dotenv()

import time
from tensorlake.image import Image

# python:3.11-slim has a proper linux/amd64 manifest on Docker Hub
# All packages baked in — agents boot ready, no runtime install
image = (
    Image(base_image="python:3.11-slim")
    .run("useradd -m tl-user")
    .run("pip install numpy pandas scikit-learn scipy statsmodels anthropic requests")
)

REGISTERED_NAME = "analyst-agent-image"

print(f"Building and registering '{REGISTERED_NAME}'...")
print("(First build is slow — Tensorlake runs pip install inside builder sandbox)")
start = time.time()

image.build(
    registered_name=REGISTERED_NAME,
    cpus=1.0,
    memory_mb=1024,
    verbose=True,
)

elapsed = time.time() - start
print(f"Done in {elapsed:.1f}s")
print(f"Registered name: {REGISTERED_NAME}")
print("All phases now use: Sandbox.create(image='analyst-agent-image')")
