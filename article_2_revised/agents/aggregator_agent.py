"""
Agent 5: Aggregator
No sandbox needed — pure LLM call that synthesises the 4 analyst reports.
Different from the other 4: its job is reasoning over structured output, not computation.
"""
from dotenv import load_dotenv
load_dotenv()

import json
from agents.base import User, Assistant, llm_call

SYSTEM_PROMPT = """You are a senior data science lead writing an executive briefing.
You have received independent analyses from 4 specialist agents.
Synthesise their findings into one concise executive summary covering:
1. Key statistical properties of the dataset
2. Main trend direction and growth rate
3. Most significant anomalies and their likely cause
4. Revenue forecast for the next 10 days
5. Overall business recommendation in 1-2 sentences.
Be specific — cite actual numbers from the reports."""


class AggregatorAgent:
    """
    Synthesises the 4 analyst reports into an executive summary.
    No sandbox — this agent only calls the LLM, does no computation.
    """

    name = "aggregator"

    def call(self, user_message: User, files=None) -> Assistant:
        reports = json.loads(user_message.content)

        sections = []
        for report in reports:
            agent_name = report.get("agent", "unknown")
            interpretation = report.get("interpretation", "")
            sections.append(f"=== {agent_name.upper()} ===\n{interpretation}")

        combined = "\n\n".join(sections)
        summary = llm_call(SYSTEM_PROMPT, combined)

        return Assistant(content=summary)
