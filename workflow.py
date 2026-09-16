import sys
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.graph import StateGraph, START, END

from state import PipelineState
from agents.scout import run_scout
from agents.coder import run_coder
from agents.tester import run_tester
from gateway.git_delivery import deliver_patch


# ----------------- NODE DEFINITIONS -----------------

def scout_node(state: PipelineState) -> dict:
    print("\n🔍 [NODE: SCOUT] Triaging vulnerability alert...")
    triage_info = run_scout(state.raw_security_alert, repo_dir=state.repo_directory)
    print(f"   -> Flaw located: {triage_info.file_path} ({triage_info.function_name})")
    return {"triage_data": triage_info}


def coder_node(state: PipelineState) -> dict:
    current_iteration = state.iteration_count + 1
    print(f"\n🛠️ [NODE: CODER] Generating patch (Iteration {current_iteration}/{state.max_iterations})...")

    error_trace = None
    if state.test_result and not state.test_result.tests_passed:
        print("   -> Feeding failure stack trace back to Coder for self-correction...")
        error_trace = state.test_result.sanitized_stack_trace

    patch_diff = run_coder(state.triage_data, error_trace=error_trace)
    return {
        "current_git_diff": patch_diff,
        "iteration_count": current_iteration
    }


def tester_node(state: PipelineState) -> dict:
    print("\n🧪 [NODE: TESTER] Applying patch and executing deterministic test suite...")
    test_eval = run_tester(
        diff_content=state.current_git_diff,
        target_file=state.triage_data.file_path,
        target_dir=state.repo_directory
    )

    if test_eval.tests_passed:
        print("   -> ✅ Tests PASSED! Patch is verified.")
    else:
        print(f"   -> ❌ Tests FAILED (Exit Code: {test_eval.exit_code}).")

    return {"test_result": test_eval}


# ----------------- CONDITIONAL ROUTING -----------------

def router_condition(state: PipelineState) -> Literal["coder", "hitl_approval", "failed_max_retries"]:
    if state.test_result and state.test_result.tests_passed:
        return "hitl_approval"

    if state.iteration_count >= state.max_iterations:
        print("\n⚠️ [MAX RETRIES REACHED] Exceeded retry budget. Escalating to human engineer.")
        return "failed_max_retries"

    print("\n🔄 [LOOP] Reflecting and routing back to Coder for self-correction...")
    return "coder"


# ----------------- HUMAN IN THE LOOP & DELIVERY -----------------

def hitl_approval_node(state: PipelineState) -> dict:
    print("\n" + "=" * 55)
    print("🛡️  HUMAN-IN-THE-LOOP APPROVAL GATE")
    print("=" * 55)
    print("Automated deterministic tests have PASSED.")
    print("Review the proposed patch before permanent branch deployment:\n")
    print("------------------ [PROPOSED DIFF] ------------------")
    print(state.current_git_diff)
    print("-----------------------------------------------------")

    choice = input("\nDo you approve committing this patch to a remediation branch? (y/n): ").strip().lower()
    approved = (choice == "y" or choice == "yes")

    if approved:
        print("✅ Patch APPROVED by human engineer. Handing off to Git Delivery...")
        delivery = deliver_patch(state)
        if delivery.get("delivered"):
            print(f"\n🎉 SUCCESS: Patch permanently committed to '{delivery['branch']}'!")
        else:
            print(f"\n⚠️ Delivery error: {delivery.get('error')}")
        return {"human_approved": True}
    else:
        print("\n🛑 Patch REJECTED by human engineer. No branch or commit created.")
        return {"human_approved": False}


def failure_node(state: PipelineState) -> dict:
    print("\n❌ Pipeline completed without an automated fix.")
    return {}


# ----------------- GRAPH COMPILATION -----------------

builder = StateGraph(PipelineState)

# Add Nodes
builder.add_node("scout", scout_node)
builder.add_node("coder", coder_node)
builder.add_node("tester", tester_node)
builder.add_node("hitl_approval", hitl_approval_node)
builder.add_node("failed_max_retries", failure_node)

# Add Edges
builder.add_edge(START, "scout")
builder.add_edge("scout", "coder")
builder.add_edge("coder", "tester")

# Conditional loop from tester
builder.add_conditional_edges(
    "tester",
    router_condition,
    {
        "coder": "coder",
        "hitl_approval": "hitl_approval",
        "failed_max_retries": "failed_max_retries"
    }
)

builder.add_edge("hitl_approval", END)
builder.add_edge("failed_max_retries", END)

workflow = builder.compile()


if __name__ == "__main__":
    initial_alert = "CRITICAL CWE-89: SQL Injection flaw identified in user database query authentication."

    initial_state = PipelineState(
        raw_security_alert=initial_alert,
        repo_directory="demo_repo",
        max_iterations=3
    )

    print(" Starting Autonomous DevSecOps Remediation Pipeline....")
    final_state = workflow.invoke(initial_state)
    print("\n--- Workflow Finished ---")