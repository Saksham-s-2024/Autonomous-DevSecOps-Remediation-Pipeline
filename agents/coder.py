import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state import VulnerabilityLocation
from gateway.router import call_llm_gateway
from gateway.guardrails import sanitize_diff_output

CODER_SYSTEM_PROMPT = """You are Patch-Engineer-Agent, an automated security remediation expert.
Your mission is to generate a minimal, surgical unified git diff that resolves the identified vulnerability without breaking existing functionality or modifying unrelated code.

STRICT INSTRUCTIONS:
1. Output ONLY a valid unified diff compatible with `git apply`.
2. Must begin with standard diff headers:
--- a/<relative_path>
+++ b/<relative_path>
3. NO markdown blocks (no ```diff), NO conversational preamble, NO closing explanations.
4. Modify ONLY the lines required to fix the vulnerability.
5. If feedback/stack trace from a failing test run is included, analyze the error and adjust your patch to satisfy the assertion.
"""

def run_coder(triage: VulnerabilityLocation, error_trace: str = None) -> str:
    # Resolve file path relative to project root
    target_abs_path = PROJECT_ROOT / triage.file_path
    
    if not target_abs_path.exists():
        raise FileNotFoundError(f"Target file not found: {target_abs_path}")

    with open(target_abs_path, "r", encoding="utf-8") as f:
        full_code = f.read()

    # Number the lines so the model knows exact line offsets
    numbered_lines = [f"{i+1:3d} | {line}" for i, line in enumerate(full_code.splitlines())]
    annotated_code = "\n".join(numbered_lines)

    user_message = f"""Target File: {triage.file_path}
Vulnerability: {triage.vulnerability_type}
Function: {triage.function_name} (Lines {triage.line_start}-{triage.line_end})
Root Cause: {triage.root_cause_summary}

Source Code:
{annotated_code}
"""

    if error_trace:
        user_message += f"\nCRITICAL: Previous patch attempt failed with this test error:\n{error_trace}\nAdjust your patch to resolve this failure."

    user_message += "\nGenerate the exact unified git diff patch now:"

    messages = [
        {"role": "system", "content": CODER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    raw_response = call_llm_gateway(messages)
    cleaned_diff = sanitize_diff_output(raw_response)
    return cleaned_diff


if __name__ == "__main__":
    from agents.scout import run_scout

    sample_alert = "CRITICAL CWE-89: Untrusted user input is directly concatenated into SQL query in user authentication/role lookup."
    print("Step 1: Running Scout triage...")
    triage_info = run_scout(sample_alert, "demo_repo")
    print(f"Scout targeted: {triage_info.file_path} -> {triage_info.function_name}")

    print("\nStep 2: Running Coder Agent...")
    patch_diff = run_coder(triage_info)
    print("--- GENERATED UNIFIED DIFF ---")
    print(patch_diff)