import os
import sys
import json
import time
import ast
import subprocess
import tempfile
from pathlib import Path

# Add project root directory to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Dynamically import project modules
try:
    import workflow
except ImportError:
    print("❌ Error: Could not import `workflow.py` from project root.")
    sys.exit(1)

BENCHMARK_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def is_valid_ast(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def run_pytest_in_dir(work_dir: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def trigger_workflow(alert: str, temp_path: Path):
    """Executes the workflow using whatever entry point workflow.py exposes."""
    if hasattr(workflow, "run_remediation_pipeline"):
        workflow.run_remediation_pipeline(alert=alert, repo_dir=str(temp_path))
    elif hasattr(workflow, "run_pipeline"):
        workflow.run_pipeline(alert=alert, repo_dir=str(temp_path))
    elif hasattr(workflow, "run"):
        workflow.run(alert=alert, repo_dir=str(temp_path))
    elif hasattr(workflow, "main"):
        workflow.main(alert=alert, repo_dir=str(temp_path))
    elif hasattr(workflow, "app"):
        initial_state = {
            "alert": alert,
            "repo_dir": str(temp_path),
            "max_retries": 3,
            "current_retry": 0,
        }
        workflow.app.invoke(initial_state)
    elif hasattr(workflow, "graph"):
        initial_state = {
            "alert": alert,
            "repo_dir": str(temp_path),
            "max_retries": 3,
            "current_retry": 0,
        }
        workflow.graph.invoke(initial_state)
    else:
        raise AttributeError(
            "Could not find a valid execution function or app in workflow.py"
        )


def execute_eval():
    if not BENCHMARK_PATH.exists():
        print(f"❌ Error: {BENCHMARK_PATH} does not exist.")
        return

    with open(BENCHMARK_PATH, "r") as f:
        benchmark = json.load(f)

    results = []

    print("=" * 65)
    print(
        f"🚀 Starting DevSecOps Agent Evaluation Suite ({len(benchmark)} Test Cases)"
    )
    print("=" * 65)

    for case in benchmark:
        case_id = case["id"]
        cwe = case["cwe"]
        is_vuln = case["is_vulnerable"]

        print(
            f"\n[EVAL] Running Case: {case_id} ({cwe}) - Expected Vulnerable: {is_vuln}"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            target_file = temp_path / case["target_file"]
            test_file = temp_path / case["test_file"]

            target_file.write_text(case["initial_code"])
            test_file.write_text(case["test_code"])

            start_time = time.time()
            ast_valid = False
            pytest_passed = False
            remediation_triggered = False
            error_message = None

            try:
                alert = f"Security Vulnerability {cwe} identified in {case['target_file']}"
                trigger_workflow(alert=alert, temp_path=temp_path)
                remediation_triggered = True
            except Exception as e:
                error_message = str(e)

            latency = round(time.time() - start_time, 2)
            patched_code = target_file.read_text()

            ast_valid = is_valid_ast(patched_code)
            pytest_passed = run_pytest_in_dir(temp_path)

            record = {
                "id": case_id,
                "cwe": cwe,
                "is_vulnerable": is_vuln,
                "remediation_triggered": remediation_triggered,
                "ast_valid": ast_valid,
                "pytest_passed": pytest_passed,
                "latency_seconds": latency,
                "error": error_message,
            }

            results.append(record)
            print(
                f"  └─ AST Valid: {ast_valid} | Tests Passed: {pytest_passed} | Latency: {latency}s"
            )

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 65)
    print(f"✅ Evaluation complete! Written to {RESULTS_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    execute_eval()