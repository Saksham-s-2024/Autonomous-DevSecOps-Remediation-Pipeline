import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state import PipelineState, VulnerabilityLocation, TestExecutionResult
from gateway.git_delivery import deliver_patch

# Construct a synthetic unified diff for testing delivery
synthetic_diff = """--- a/demo_repo/app.py
+++ b/demo_repo/app.py
@@ -17,2 +17,2 @@
-    query = f"SELECT role FROM users WHERE username = '{username}'"
-    cursor.execute(query)
+    query = "SELECT role FROM users WHERE username = ?"
+    cursor.execute(query, (username,))
"""

# Create a mock state representing a successful pipeline run
mock_state = PipelineState(
    raw_security_alert="CRITICAL CWE-89: SQL Injection in authentication query.",
    repo_directory="demo_repo",
    triage_data=VulnerabilityLocation(
        file_path="demo_repo/app.py",
        function_name="get_user_role",
        line_start=17,
        line_end=18,
        vulnerability_type="CWE-89: SQL Injection",
        root_cause_summary="Direct f-string query formatting without parameterization allows arbitrary SQL injection."
    ),
    current_git_diff=synthetic_diff,
    iteration_count=1,
    test_result=TestExecutionResult(
        tests_passed=True,
        exit_code=0,
        raw_output="1 passed in 0.05s",
        sanitized_stack_trace=None
    )
)

print("🚀 Executing isolated delivery verification...")
result = deliver_patch(mock_state)

print("\n--- Delivery Result ---")
print(result)