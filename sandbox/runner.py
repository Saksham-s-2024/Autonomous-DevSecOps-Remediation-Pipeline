import subprocess
import os

def run_tests(target_dir: str = "demo_repo") -> dict:
    """
    Runs pytest on the target directory and extracts deterministic signals.
    """
    result = subprocess.run(
        ["pytest", target_dir, "-q"],
        capture_output=True,
        text=True
    )
    
    passed = (result.returncode == 0)
    
    raw_output = result.stdout or result.stderr
    condensed_lines = []
    capture = False
    for line in raw_output.splitlines():
        if "FAILURES" in line or "FAILED" in line:
            capture = True
        if capture:
            condensed_lines.append(line)
            
    sanitized_trace = "\n".join(condensed_lines) if condensed_lines else raw_output

    return {
        "passed": passed,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "sanitized_trace": sanitized_trace
    }

if __name__ == "__main__":
    print("Testing programmatic test runner...")
    output = run_tests("demo_repo")
    print(f"Tests Passed: {output['passed']}")
    print(f"Exit Code   : {output['exit_code']}")
    print(f"Traceback   :\n{output['sanitized_trace']}")