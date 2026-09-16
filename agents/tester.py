import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sandbox.patcher import apply_diff_patch, backup_file, rollback_file
from sandbox.runner import run_tests
from state import TestExecutionResult

def run_tester(
    diff_content: str, 
    target_file: str = "demo_repo/app.py", 
    target_dir: str = "demo_repo"
) -> TestExecutionResult:
    """
    Applies the patch, runs the test suite, captures deterministic results,
    and rolls back changes to keep the repository pristine.
    """
    target_abs = PROJECT_ROOT / target_file
    
    original_code = backup_file(str(target_abs))

    try:
        patch_status = apply_diff_patch(diff_content, target_dir=target_dir)

        if not patch_status["success"]:
            return TestExecutionResult(
                tests_passed=False,
                exit_code=2,
                sanitized_stack_trace=f"Git Apply Failed: {patch_status['error']}"
            )

        test_run = run_tests(str(PROJECT_ROOT / target_dir))

        return TestExecutionResult(
            tests_passed=test_run["passed"],
            exit_code=test_run["exit_code"],
            sanitized_stack_trace=None if test_run["passed"] else test_run["sanitized_trace"]
        )

    finally:
        rollback_file(str(target_abs), original_code)


if __name__ == "__main__":
    from agents.scout import run_scout
    from agents.coder import run_coder

    sample_alert = "CRITICAL CWE-89: SQL Injection detected in user authentication/role lookup."
    
    print("--- 1. Running Scout ---")
    triage = run_scout(sample_alert, "demo_repo")
    print(f"Located: {triage.file_path} at line {triage.line_start}")

    print("\n--- 2. Running Coder ---")
    diff = run_coder(triage)
    print("Generated Diff:\n", diff)

    print("\n--- 3. Running Tester ---")
    result = run_tester(diff, target_file=triage.file_path)
    print("Tests Passed :", result.tests_passed)
    print("Exit Code    :", result.exit_code)
    if not result.tests_passed:
        print("Failure Trace:\n", result.sanitized_stack_trace)