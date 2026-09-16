import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state import VulnerabilityLocation
from gateway.router import call_llm_gateway

SCOUT_SYSTEM_PROMPT = """You are SecOps-Scout-Agent, a specialized software triage expert.
Your mission is to read incoming vulnerability alerts, inspect the source files provided, and pinpoint the exact location of the security flaw.

STRICT CONSTRAINTS:
1. You MUST respond ONLY with a valid JSON object matching this schema:
{
  "file_path": "<relative path to vulnerable file, e.g. demo_repo/app.py>",
  "function_name": "<name of vulnerable function>",
  "line_start": <integer start line number>,
  "line_end": <integer end line number>,
  "vulnerability_type": "<e.g., CWE-89: SQL Injection>",
  "root_cause_summary": "<concise technical explanation>"
}
2. Output NO markdown fences (no ```json), NO conversational preamble, NO closing explanations. Only raw JSON.
3. Target only the root cause source file, never test files or configuration scripts.
"""

def run_scout(raw_alert: str, repo_dir: str = "demo_repo") -> VulnerabilityLocation:
    target_repo = PROJECT_ROOT / repo_dir

    code_context = {}
    for root, _, files in os.walk(target_repo):
        for file in files:
            if file.endswith(".py") and not file.startswith("test_"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                with open(abs_path, "r", encoding="utf-8") as f:
                    code_context[rel_path] = f.read()

    if not code_context:
        raise FileNotFoundError(f"No source Python files found in directory: {target_repo}")

    context_blocks = []
    for path, code in code_context.items():
        numbered_lines = [f"{i+1:3d} | {line}" for i, line in enumerate(code.splitlines())]
        context_blocks.append(f"=== File: {path} ===\n" + "\n".join(numbered_lines))

    context_str = "\n\n".join(context_blocks)

    user_message = f"""Security Alert:
{raw_alert}

Target Codebase:
{context_str}

Analyze the alert and codebase. Pinpoint the vulnerable file, function, and lines. Output valid raw JSON only."""

    messages = [
        {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    raw_response = call_llm_gateway(messages)

    cleaned_text = raw_response.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.split("```")[1]
        if cleaned_text.startswith("json"):
            cleaned_text = cleaned_text[4:]
        cleaned_text = cleaned_text.strip()

    data = json.loads(cleaned_text)
    return VulnerabilityLocation(**data)


if __name__ == "__main__":
    sample_alert = "CRITICAL CWE-89: Untrusted user input is directly concatenated into SQL query in user authentication/role lookup."
    
    print("Running Scout Agent on 'demo_repo'...\n")
    location = run_scout(sample_alert, repo_dir="demo_repo")
    
    print("--- SCOUT TRIAGE REPORT ---")
    print(f"Target File : {location.file_path}")
    print(f"Function    : {location.function_name}")
    print(f"Lines       : {location.line_start} to {location.line_end}")
    print(f"Flaw Type   : {location.vulnerability_type}")
    print(f"Root Cause  : {location.root_cause_summary}")