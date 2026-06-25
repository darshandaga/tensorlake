from dotenv import load_dotenv
load_dotenv()

import time
from tensorlake.sandbox import Sandbox

REGISTERED_NAME = "analyst-agent-image"

print(f"=== Verifying image: {REGISTERED_NAME} ===")
print("Booting a sandbox from the registered image...")

start = time.time()
sb = Sandbox.create(image=REGISTERED_NAME)
elapsed = round(time.time() - start, 2)

print(f"Sandbox {sb.sandbox_id} booted in {elapsed}s")

try:
    result = sb.run("python3", ["-c",
        "import numpy, pandas, sklearn, scipy, statsmodels, anthropic, requests; "
        "print('numpy', numpy.__version__); "
        "print('pandas', pandas.__version__); "
        "print('scipy', scipy.__version__); "
        "print('anthropic', anthropic.__version__); "
        "print('ALL PACKAGES OK')"
    ])
    print(result.stdout.strip())
    if result.stderr:
        print("STDERR:", result.stderr)
finally:
    sb.terminate()

if "ALL PACKAGES OK" in result.stdout:
    print(f"\nREGISTERED IMAGE: {REGISTERED_NAME}")
    print(f"SANDBOX ID: {sb.sandbox_id}")
    print(f"BOOT TIME: {elapsed}s")
    print("STATUS: VERIFIED")
else:
    print("\nVERIFICATION FAILED — re-run build_agent_image.py")
