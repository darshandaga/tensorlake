from dotenv import load_dotenv
load_dotenv()

import os
import time
import json
from dataclasses import dataclass
from tensorlake.sandbox import Sandbox
from anthropic import Anthropic

AGENT_IMAGE = "analyst-agent-image"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class User:
    content: str


@dataclass
class Assistant:
    content: str


def boot_sandbox(max_retries: int = 12, retry_delay: float = 8.0) -> Sandbox:
    """
    Boot a fresh sandbox from the registered image.
    Retries on quota errors — free tier allows only 1 sandbox at a time,
    so agents running in parallel will queue here until a slot opens.
    """
    for attempt in range(max_retries):
        try:
            return Sandbox.create(image=AGENT_IMAGE, timeout_secs=300)
        except Exception as e:
            if "quota" in str(e).lower() and attempt < max_retries - 1:
                print(f"  [boot_sandbox] Quota hit — waiting {retry_delay}s then retrying "
                      f"(attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                raise
    raise RuntimeError("boot_sandbox: failed after max retries")


def write_data_to_sandbox(sb: Sandbox, csv_content: str):
    """Write the shared dataset into the sandbox workspace."""
    sb.write_file("/workspace/data/dataset.csv", csv_content.encode())


def run_python_in_sandbox(sb: Sandbox, code: str) -> str:
    """Execute Python code inside the sandbox and return stdout."""
    result = sb.run("python3", ["-c", code])
    if result.stderr:
        return f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"
    return result.stdout.strip()


def llm_call(system_prompt: str, user_content: str) -> str:
    """Single Anthropic API call — used by each agent for its analysis."""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )
    return response.content[0].text
