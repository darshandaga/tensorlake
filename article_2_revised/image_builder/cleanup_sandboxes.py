from dotenv import load_dotenv
load_dotenv()

from tensorlake.sandbox import Sandbox

sandboxes = list(Sandbox.list())

if not sandboxes:
    print("No running sandboxes found.")
else:
    for info in sandboxes:
        sb_id = info.sandbox_id
        print(f"Terminating {sb_id}...")
        sb = Sandbox(sb_id)
        sb.terminate()
        print(f"  Done.")
    print(f"Terminated {len(sandboxes)} sandbox(es).")
